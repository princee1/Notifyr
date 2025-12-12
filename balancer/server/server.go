package server

import (
	"balancer/container"
	"balancer/middleware"
	bws "balancer/websocket"
	"fmt"
	"log"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
)

type NotifyrBalancer struct {
	Container *container.Container
	Fiber     *fiber.App
}

func (balancer *NotifyrBalancer) LoadRoute() {

}

func (balancer *NotifyrBalancer) LoadMiddleWare() {
	metadata := middleware.MetaDataMiddleware{SecurityService: balancer.Container.GetSecurityService()}
	active := middleware.ActiveMiddleware{HealthService: balancer.Container.GetHealthService()}
	split := middleware.SplitProxyMiddleware{ProxyService: balancer.Container.GetProxyAgentService(), ConfigService: balancer.Container.GetConfigService()}
	proxy := middleware.ProxyMiddleware{ProxyService: balancer.Container.GetProxyAgentService()}

	balancer.Fiber.Use(metadata.Middleware)
	balancer.Fiber.Use(active.Middleware)
	balancer.Fiber.Use(split.Middleware)
	balancer.Fiber.Use(proxy.Middleware)
}

func (balancer *NotifyrBalancer) LoadWebSocket() {
	ws := bws.WebSocket{
		HealthService: balancer.Container.GetHealthService(),
		ConfigService: balancer.Container.GetConfigService(),
		ProxyService: balancer.Container.GetProxyAgentService(),
	}

	balancer.Fiber.Use("/ws/:path/", ws.WSMiddleware)
	balancer.Fiber.Get("/ws/:path/", websocket.New(ws.WSHandler))
}

func (balancer *NotifyrBalancer) Start() {

	if !balancer.Container.GetConfigService().HasApps() {
		errMess := fmt.Sprintf("Failed to start server: %v", "No Notifyr App Created")
		log.Print(errMess)
		panic(errMess)
	}
	balancer.Container.GetHealthService().WFNotifyrConn()
	balancer.Container.Welcome(2)

	if err := balancer.Fiber.Listen(balancer.Container.GetConfigService().Addr()); err != nil {
		log.Printf("Failed to start server: %v", err)
		panic(err)
	}
}

func (balancer *NotifyrBalancer) Shutdown() {

	<-*balancer.Container.Quit

	log.Println("Shutting down server...")

	if err := balancer.Fiber.Shutdown(); err != nil {
		log.Fatal("Server Shutdown Failed:", err)
	}
	balancer.Container.GetHealthService().Disconnect()
	balancer.Container.WaitWS()
	log.Println("Server gracefully stopped.")
}
