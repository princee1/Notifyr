package service

import (
	"fmt"
	"log"
	"net/http"
	"net/url"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)


const SECOND int64 = 1_000_000_000

const MAX_RETRY uint8 = 10
const PING_FREQ time.Duration = time.Duration(180*SECOND)
const RETRY_FREQ time.Duration = time.Duration(20*SECOND)
const PERMISSION_ROUTE = "ping-pong/permission/_pong_/"

const WS_AUTH_KEY = "X-WS-Auth-Key"

type AppSpec struct {
	CpuCore      uint
	ProcessCount uint
	Ram          uint
	Weight       float64
}

type NotifyrApp struct {
	Id         string
	InstanceId string
	parent_pid string
	address    string
	port       uint
	Roles      []string
	Spec       AppSpec
	Active     bool
}

type PingPongClient struct {
	Name            string
	Connector       *websocket.Conn
	URL             string
	connected       bool
	healthService 	*HealthService
	securityService *SecurityService
	permission		string
}


func (client *PingPongClient) RequestPermission() error {
	u, err := url.Parse(client.URL)
	if err != nil {
		return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
	}
	var app NotifyrApp
	permission,err := client.securityService.getPongWsPermission(*u,client.Name,&app)

	if err != nil {
		return fmt.Errorf("failed to request permission for %s: %v", client.Name, err)
	}
	if err != nil {
		return fmt.Errorf("failed to decode permission response for %s: %v", client.Name, err)
	}
	
	client.permission = permission
	client.healthService.notifyrApps[client.Name] = app
	return nil
}

func (client *PingPongClient) Disconnect() {

	defer client.RemoveActiveConnection()

	err := client.Connector.Close()
	if err != nil {
		log.Printf("failed to close connection for %s: %v", client.Name, err)
		return
	}
	client.connected = false
	log.Printf("[%s] Disconnected from %s", client.Name, client.URL)
}

func (client *PingPongClient) RemoveActiveConnection() {
	if err:=client.healthService.RemoveActiveConnection(client.Name); err !=nil {

	}
}

func (client *PingPongClient) Connect()error {
	if err :=client.RequestPermission(); err != nil{
		return err
	}
	return client.connectWS()
}

func (client *PingPongClient) connectWS() error {


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
		
		url:= fmt.Sprintf("ws://%v:%v",u.Hostname(),u.Port())
		header := http.Header{}
		header.Add(WS_AUTH_KEY,client.permission)
		_conn, _, err := websocket.DefaultDialer.Dial(url,header)
		if err != nil {
			retry++;
			if retry == int(MAX_RETRY){
				return fmt.Errorf("failed to connect after %v retry... %s: %v",MAX_RETRY,client.Name, err)
			}

			log.Printf("Failed to connected to WS (%s): With attempt %v / %v: Reason %v",client.Name,retry,MAX_RETRY,err)
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
				return
			}
		}
	}

}

type HealthService struct {
	notifyrApps map[string]NotifyrApp
	ppClient     map[string]PingPongClient
	SecurityService *SecurityService
	ConfigService *ConfigService
	active_pp uint
	mu sync.RWMutex

}

func (health *HealthService) CreatePPClient(proxyService *ProxyAgentService) {

	health.notifyrApps = map[string]NotifyrApp{}
	health.ppClient = map[string]PingPongClient{}

	for index, value := range health.ConfigService.URLS {
		name := fmt.Sprintf("Notifyr Instance %v", index)
		ppClient := PingPongClient{Name: name, URL: value, healthService: health, securityService: health.SecurityService}
		if err := ppClient.Connect(); err != nil {
			log.Printf("Error connecting PingPongClient %s: %v at addr %v", name, err,ppClient.URL)
			continue
		}
		health.ppClient[value] = ppClient
	}
}

func (health *HealthService) StartConnection() {
	for _,client := range health.ppClient{
		client.Run()
		health.active_pp++;
	}
}

func (health *HealthService) AggregateHealth() {

}

func (health *HealthService) ActiveConnection() uint{
	health.mu.RLock()
	defer health.mu.RUnlock()
	return health.active_pp
}

func (health *HealthService) RemoveActiveConnection(Name string) error{
	health.mu.Lock()
	defer health.mu.Unlock()
	na, ok :=health.notifyrApps[Name]
	if !ok {

	}else{
		na.Active = false
		health.active_pp--;
	}
	return nil
}
