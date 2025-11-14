package balancerWebsocket

import (
	service "balancer/internal/services"
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/gofiber/fiber/v2"
	fiberWebsocket "github.com/gofiber/websocket/v2"
	"github.com/gorilla/websocket"
)

type WebSocket struct{
	HealthService *service.HealthService
	ConfigService *service.ConfigService
	ProxyService *service.ProxyAgentService
}

func (ws *WebSocket) WSMiddleware(c *fiber.Ctx) error {
	if fiberWebsocket.IsWebSocketUpgrade(c) {
		c.Locals("allowed", true)
		c.Locals("headers", c.GetReqHeaders())
		return c.Next()
	}
	return fiber.ErrUpgradeRequired
}

func (ws *WebSocket) WSHandler(c *fiberWebsocket.Conn) {
	// Extract the path parameter
	path := c.Params("path")
	if path == "" {
		log.Println("Path parameter is missing")
		c.Close()
		return
	}

	// Extract the X-Protocol-WS header
	protocol := c.Query("X-Protocol-WS", "json")

	headers := http.Header{}
	if h, ok := c.Locals("headers").(map[string]string); ok {
		for key, value := range h {
			headers.Add(key, value)
		}
	}

	internal_server:=ws.ProxyService.ChooseServer(false)[0]
	internal_server = fmt.Sprintf("ws://%v/%v",internal_server,path)

	internalConn, _, err := websocket.DefaultDialer.Dial(internal_server, headers)
	if err != nil {
		log.Printf("Failed to connect to internal WebSocket server: %v\n", err)
		c.Close()
		return
	}
	defer internalConn.Close()

	// Channel to handle bidirectional communication
	done := make(chan struct{})

	// Forward messages from the internal WebSocket server to the external client
	go func() {
		defer close(done)
		for {
			_, message, err := internalConn.ReadMessage()
			if err != nil {
				log.Printf("Error reading from internal WebSocket: %v\n", err)
				break
			}

			// Send the message back to the external client
			if protocol == "text" {
				err = c.WriteMessage(fiberWebsocket.TextMessage, message)
			} else {
				var jsonData map[string]interface{}
				if err := json.Unmarshal(message, &jsonData); err != nil {
					log.Printf("Error unmarshalling JSON: %v\n", err)
					break
				}
				err = c.WriteJSON(jsonData)
			}

			if err != nil {
				log.Printf("Error writing to external WebSocket: %v\n", err)
				break
			}
		}
	}()

	// Forward messages from the external client to the internal WebSocket server
	for {
		_, message, err := c.ReadMessage()
		if err != nil {
			log.Printf("Error reading from external WebSocket: %v\n", err)
			break
		}

		err = internalConn.WriteMessage(fiberWebsocket.TextMessage, message)
		if err != nil {
			log.Printf("Error writing to internal WebSocket: %v\n", err)
			break
		}
	}

	<-done
}
