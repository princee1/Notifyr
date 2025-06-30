package service

import (
	"fmt"
	"log"
	"net/url"
	"time"
	"github.com/gorilla/websocket"
)

const MAX_RETRY uint8 = 10
const PING_FREQ time.Duration = time.Duration(10)
const RETRY_FREQ time.Duration = time.Duration(10)

type PingPongClient struct {
	Name            string
	Connector       *websocket.Conn
	URL             string
	connected       bool
	proxyService    *ProxyAgentService
	securityService *SecurityService
}

func (client *PingPongClient) RequestPermission() error {

	// u, err := url.Parse(client.URL)
	// if err != nil {
	// 	return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
	// }
	// 
	return nil
}

func (client *PingPongClient) Disconnect() {

	err := client.Connector.Close()
	if err != nil {
		log.Printf("failed to close connection for %s: %v", client.Name, err)
		return
	}
	client.connected = false
	log.Printf("[%s] Disconnected from %s", client.Name, client.URL)
	return
}

func (client *PingPongClient) RemoveActiveConnection() {

}

func (client *PingPongClient) Connect()error {
	client.RequestPermission()
	return client.ConnectWS(nil)
}

func (client *PingPongClient) ConnectWS(header any) error {
	ticker := time.NewTicker(RETRY_FREQ)
	defer ticker.Stop()
	var conn *websocket.Conn;
	var retry int = 0;

	for {
		<-ticker.C

		u, err := url.Parse(client.URL)
		if err != nil {
			return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
		}
		_conn, _, err := websocket.DefaultDialer.Dial(u.String(),nil)
		if err != nil {
			retry++;
			if retry == int(MAX_RETRY){
				return fmt.Errorf("failed to connect %s: %v", client.Name, err)
			}
			continue
		}else{
			conn = _conn
			break
		}
	}

	client.Connector = conn
	client.connected = true
	client.InitCallback()
	log.Printf("[%s] Connected to %s", client.Name, client.URL)
	return nil
}

func (client *PingPongClient) InitCallback(){

	client.Connector.SetPongHandler(func(appData string) error {
		_ = client.Connector.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	client.Connector.SetCloseHandler(func(code int, text string) error {

		// TODO remove the connection from the map of active connection

		client.connected = false
		return nil
	})
}

func (client *PingPongClient) ReadPong() {
	// Implement the logic for reading pong messages here
	go func() {
		for {
			// client.Connector.ReadJSON()
			_, mess, err := client.Connector.ReadMessage()
			if err != nil {
				log.Printf("[%s] Read error: %v", client.Name, err)
				// TODO disconnect?
				return
			}
			log.Printf("[%s] Received: %s", client.Name, mess)
		}
	}()
}

func (client *PingPongClient) Run() {

	defer client.Disconnect()
	client.ReadPong()
	client.Ping()

}

func (client *PingPongClient) Ping() {

	ticker := time.NewTicker(PING_FREQ)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			err := client.Connector.WriteMessage(websocket.PingMessage, nil)
			if err != nil {
				log.Printf("[%s] Ping error: %v", client.Name, err)
				client.Disconnect()
				client.RemoveActiveConnection()
				return
			}
		}
	}

}

type HealthService struct {
	PPClient     map[string]PingPongClient
	proxyService *ProxyAgentService
	securityService *SecurityService
	active_pp uint
}


func (health *HealthService) CreatePPClient(apps *[]string) {

	// for index,value :=range *apps{

	// 	ppClient:= PingPongClient{Name="Instance",URL=value,proxyService=health.proxyService,securityService=health.securityService}
	// 	health.PPClient[value] = ppClient
	// 	if ppClient.Connect() != nil{

	// 		continue
	// 	}
	// 	ppClient.Run()
	// }
}

func (health *HealthService) StartConnection() {

}

func (health *HealthService) AggregateHealth() {

}
