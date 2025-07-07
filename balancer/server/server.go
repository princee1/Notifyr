package server

import (
	"balancer/container"
	"balancer/middleware"
	"fmt"
	"log"

	"github.com/gofiber/fiber/v2"
)

type NotifyrBalancer struct {
	Container *container.Container
	Fiber     *fiber.App
}

func (balancer *NotifyrBalancer) LoadRoute() {

}

func (balancer *NotifyrBalancer) LoadMiddleWare() {
	access := middleware.AccessMiddleware{SecurityService: balancer.Container.GetSecurityService()}
	metadata := middleware.MetaDataMiddleware{SecurityService: balancer.Container.GetSecurityService()}
	proxy := middleware.ProxyMiddleware{ProxyService: balancer.Container.GetProxyAgentService()}

	balancer.Fiber.Use(metadata.Middleware)
	balancer.Fiber.Use(access.Middleware)
	balancer.Fiber.Use(proxy.Middleware)
}

func (balancer *NotifyrBalancer) LoadWebSocket() {

}

func (balancer *NotifyrBalancer) Start() {

	if !balancer.Container.GetConfigService().HasApps() {
		errMess := fmt.Sprintf("Failed to start server: %v", "No Notifyr App Created")
		log.Print(errMess)
		panic(errMess)
	}
	balancer.Container.GetHealthService().WFNotifyrConn()
	balancer.Container.Welcome(10)
	
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
