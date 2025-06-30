package service

import (
	"fmt"
	"log"
	"net/url"
	"time"

	"github.com/gorilla/websocket"
)

type PingPongClient struct {
	Name string;
	instanceId string;
	Connector *websocket.Conn;
	URL string;
	PingFreq time.Duration;
	RetryFreq time.Duration;
	connected bool;
	proxyService *ProxyAgentService;
	securityService *SecurityService;
}


func (client *PingPongClient) RequestPermission(){

}

func (client *PingPongClient) PreparePermission(header any) {


}

func (client *PingPongClient) Disconnect(){

}

func (client *PingPongClient) RemoveActiveConnection(){

}

func (client *PingPongClient) Connect(header any) error {

	u, err := url.Parse(client.URL)
	if err != nil {
		return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
	}

	conn, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return fmt.Errorf("failed to connect %s: %v", client.Name, err)
	}
	client.Connector = conn

	client.Connector.SetPongHandler(func(appData string) error {
		_ = client.Connector.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	client.Connector.SetCloseHandler(func(code int, text string) error {

		// TODO remove the connection from the map of active connection
		
		client.connected = false
		return nil
	})
	client.connected = true

	log.Printf("[%s] Connected to %s", client.Name, client.URL)
	return nil
}

func (client *PingPongClient) ReadPong() {
	// Implement the logic for reading pong messages here

	go func() {
		for {
			// client.Connector.ReadJSON()
			_, mess, err := client.Connector.ReadMessage()
			if err != nil {
				log.Printf("[%s] Read error: %v", client.Name, err)
				return
			}
			log.Printf("[%s] Received: %s", client.Name, mess)
		}
	}()
}

func (client *PingPongClient) Run(){

	defer client.Connector.Close()
	client.ReadPong()
	client.Ping()

}

func (client *PingPongClient) Ping(){

	ticker := time.NewTicker(client.PingFreq)
	defer ticker.Stop()

	for {
		select {
		case <- ticker.C:
			err := client.Connector.WriteMessage(websocket.PingMessage,nil)
			if err!= nil {
				log.Printf("[%s] Ping error: %v", client.Name, err)
				client.Disconnect()
				client.RemoveActiveConnection()
				return 
			}
		}
	}
	
}


type HealthService struct {
	heartbeat float64;
	PPClient map[string]PingPongClient;
	proxyService *ProxyAgentService;
}


func (health *HealthService) CreatePPClient(){

}

func (health *HealthService) StartConnection(){

}

func (health *HealthService) AggregateHealth(){
	
}

