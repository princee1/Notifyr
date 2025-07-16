package service

import (
	"balancer/internal/utils"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const SECOND int64 = 1_000_000_000

const MAX_RETRY uint8 = 10

const UNEXPECTED_PEER_READ_ERROR = 4001
const PING_FREQ time.Duration = time.Duration(60 * SECOND)
const RETRY_FREQ time.Duration = time.Duration(20 * SECOND)

const PERMISSION_ROUTE = "ping-pong/permission/_pong_/"
const PONG_WS_ROUTE = "pong/"
const WS_AUTH_KEY = "X-WS-Auth-Key"

type AppSpec struct {
	CpuCore      uint
	ProcessCount uint
	Ram          uint
	Weight       float64
}

type NotifyrApp struct {
	Id           string
	InstanceId   string
	parent_pid   string
	Roles        []string
	Capabilities []string
	Spec         AppSpec
}

const (
	TO_CONNECT = iota
	TO_RUN
	TO_QUIT
	TO_IDLE
)

type PingPongClient struct {
	Name            string
	URL             string
	Connected       bool
	IsStarted       bool
	healthService   *HealthService
	securityService *SecurityService
	permission      string
	app             *NotifyrApp
	connector       *websocket.Conn
	state           int
	mu              sync.RWMutex
}

func (client *PingPongClient) RequestPermission() error {
	u, err := url.Parse(client.URL)
	if err != nil {
		return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
	}
	var app NotifyrApp
	permission, err := client.securityService.getPongWsPermission(*u, client.Name, &app)

	if err != nil {
		return fmt.Errorf("failed to request permission for %s: %v", client.Name, err)
	}

	client.permission = permission
	client.app = &app
	client.IsStarted = true
	return nil
}

func (client *PingPongClient) Disconnect(byMe bool, code int, reason string) {

	client.mu.Lock()

	if !client.Connected {
		return
	}
	client.Connected = false
	if byMe {
		client.state = TO_QUIT
	} else {

		switch code {
		case 1000:
			client.state = TO_QUIT

		case 1001:
			client.state = TO_QUIT

		case 1012:
			client.state = TO_CONNECT

		case UNEXPECTED_PEER_READ_ERROR:
			client.state = TO_CONNECT

		default:
			client.state = TO_QUIT
		}
	}
	client.mu.Unlock()

	err := client.connector.Close()
	if err != nil {
		log.Printf("failed to close connection for %s: %v", client.Name, err)
		client.state = TO_QUIT
		return
	}
	log.Printf("[%s] Disconnected from %s", client.Name, client.URL)
}

func (client *PingPongClient) RemoveActiveConnection() {
	if err := client.healthService.RemoveActiveConnection(client.Name); err != nil {

	}
}

func (client *PingPongClient) Connect() error {
	if err := client.RequestPermission(); err != nil {
		return err
	}
	return client.connectWS()
}

func (client *PingPongClient) connectWS() error {

	ticker := time.NewTicker(RETRY_FREQ)
	defer ticker.Stop()
	var conn *websocket.Conn
	var retry int = 0

	for {
		<-ticker.C

		u, err := url.Parse(client.URL)
		if err != nil {
			return fmt.Errorf("invalid URL for %s: %v", client.Name, err)
		}

		url := fmt.Sprintf("ws://%v:%v/%v", u.Hostname(), u.Port(), PONG_WS_ROUTE)
		header := http.Header{}
		header.Add(WS_AUTH_KEY, client.permission)
		_conn, _, err := websocket.DefaultDialer.Dial(url, header)
		if err != nil {
			retry++
			if retry == int(MAX_RETRY) {
				return fmt.Errorf("failed to connect after %v retry... %s: %v", MAX_RETRY, client.Name, err)
			}

			log.Printf("Failed to connected to WS (%s): With attempt %v / %v: Reason %v", client.Name, retry, MAX_RETRY, err)
			continue
		} else {

			conn = _conn
			break
		}
	}

	client.connector = conn

	client.mu.Lock()
	client.Connected = true
	defer client.mu.Unlock()

	client.initCallback()
	log.Printf("[%s] Connected to %s", client.Name, client.URL)
	client.healthService.UnBlock()

	return nil
}

func (client *PingPongClient) initCallback() {

	client.connector.SetPongHandler(func(appData string) error {
		_ = client.connector.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	client.connector.SetCloseHandler(func(code int, reason string) error {
		// 1012
		log.Printf("[%s] Server closed connection With close Handler. Code: %d, Reason: %s", client.Name, code, reason)
		client.Disconnect(false, code, reason)
		return nil
	})
}

func (client *PingPongClient) Pong(wg *sync.WaitGroup) {
	// Implement the logic for reading pong messages here
	defer wg.Done()
	for {
		client.mu.RLock()
		if !client.Connected {
			client.mu.RUnlock()
			return
		}
		client.mu.RUnlock()

		_, _, err := client.connector.ReadMessage()
		if err != nil {
			// Handle normal WebSocket close codes
			if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
				closeErr := err.(*websocket.CloseError)

				switch closeErr.Code {
				case websocket.CloseNormalClosure:
					log.Printf("[%s] Client initiated normal close: %v", client.Name, err)
				case websocket.CloseGoingAway:
					log.Printf("[%s] Server initiated close (going away): %v", client.Name, err)
				default:
					log.Printf("[%s] Normal closure with unhandled code: %v", client.Name, err)
				}

			} else if websocket.IsUnexpectedCloseError(err) {
				// Unexpected close (like network errors)
				log.Printf("[%s] Unexpected connection close: %v", client.Name, err)

			} else {
				// Other non-WebSocket read errors
				if errors.Is(err, net.ErrClosed) || strings.Contains(err.Error(), "use of closed network connection") {
					// log.Print(" Connection closed by client.")
				} else {
					client.Disconnect(false, UNEXPECTED_PEER_READ_ERROR, fmt.Sprintf("%v", err))
					log.Printf("[%s] Read error: %v", client.Name, err)

				}
			}
			return
		}
		// log.Printf("[%s] Received: %s", client.Name, mess)
	}
}

func (client *PingPongClient) Run(wg *sync.WaitGroup) {
	wg.Add(2)
	go client.Pong(wg)
	go client.Ping(wg)
}

func (client *PingPongClient) Ping(wg *sync.WaitGroup) {
	//go func(){
	ticker := time.NewTicker(PING_FREQ)
	defer ticker.Stop()
	defer wg.Done()
	for {
		select {
		case <-ticker.C:
			client.mu.RLock()
			if !client.Connected {
				client.mu.RUnlock()
				return
			}
			client.mu.RUnlock()
			err := client.connector.WriteMessage(websocket.TextMessage, []byte("PING"))
			if err != nil {
				log.Printf("[%s] Ping error: %v", client.Name, err)
				return
			}
		}
	}
	//}()
}

func (client *PingPongClient) Wait(wg *sync.WaitGroup) {
	wg.Wait()
	// TODO change the code
}

func (client *PingPongClient) StateMachine() {
	for {
		var wg sync.WaitGroup

		switch client.state {

		case TO_CONNECT:
			if err := client.Connect(); err != nil {
				log.Printf("Error connecting PingPongClient %s: %v at addr %v", client.Name, err, client.URL)
				client.state = TO_QUIT
			} else {
				client.healthService.mu.Lock()
				client.healthService.activePpConnection++
				client.healthService.mu.Unlock()
				client.state = TO_RUN
			}

		case TO_RUN:
			client.Run(&wg)
			client.Wait(&wg)

		case TO_QUIT:
			fmt.Printf("[%v] Ping Pong Connector Is Terminated\n", client.Name)
			return

		case TO_IDLE:

		}
	}
}

type WaitForConnection struct {
	wait      chan struct{}
	IsStarted bool
	mu        sync.RWMutex
}

type HealthService struct {
	ppClient           map[string]*PingPongClient
	SecurityService    *SecurityService
	ConfigService      *ConfigService
	activePpConnection uint
	mu                 sync.RWMutex
	wFConn             *WaitForConnection
}

func (health *HealthService) WFInitChan() {
	wfc := WaitForConnection{wait: make(chan struct{})}
	health.wFConn = &wfc
}

func (health *HealthService) UnBlock() {
	health.wFConn.mu.RLock()
	if health.wFConn.IsStarted {
		health.wFConn.mu.RUnlock()
		return
	}
	health.wFConn.mu.RUnlock()

	health.wFConn.mu.Lock()
	if !health.wFConn.IsStarted {
		health.wFConn.IsStarted = true
		health.wFConn.wait <- struct{}{}
	}
	health.wFConn.mu.Unlock()
}

func (health *HealthService) InitPingPongConnection(proxyService *ProxyAgentService) *sync.WaitGroup {

	health.ppClient = map[string]*PingPongClient{}
	var wg sync.WaitGroup
	for index, value := range health.ConfigService.URLS {
		name := fmt.Sprintf("Notifyr Instance %v", index)
		ppClient := PingPongClient{Name: name, URL: value, healthService: health, securityService: health.SecurityService, state: TO_CONNECT}
		hashed_value := utils.HashURL(value)
		health.ppClient[hashed_value] = &ppClient
		wg.Add(1)
		go func() {
			defer wg.Done()
			ppClient.StateMachine()
		}()
	}
	return &wg
}

func (health *HealthService) ActiveServer() []string {
	var servers = []string{}
	health.mu.RLock()
	defer health.mu.RUnlock()

	for _, client := range health.ppClient {
		client.mu.RLock()
		isConnected := client.Connected
		client.mu.RUnlock()

		if isConnected && client.IsStarted {
			servers = append(servers, client.URL)
		}

	}

	return servers
}

func (health *HealthService) AggregateHealth() {

}

func (health *HealthService) ActiveConnection() uint {
	health.mu.RLock()
	defer health.mu.RUnlock()
	return health.activePpConnection
}

func (health *HealthService) RemoveActiveConnection(Name string) error {
	health.mu.Lock()
	defer health.mu.Unlock()
	_, ok := health.ppClient[Name]
	if !ok {
		return fmt.Errorf("client with name %s not found", Name)
	} else {
		health.activePpConnection--
	}
	return nil
}

func (health *HealthService) WFNotifyrConn() {
	<-health.wFConn.wait
}

func (health *HealthService) Disconnect() error {

	health.mu.Lock()
	defer health.mu.Unlock()

	for _, client := range health.ppClient {
		client.Disconnect(true, -1, "")
	}

	return nil
}
