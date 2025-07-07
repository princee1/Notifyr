package main

import (
	"balancer/container"
	"balancer/server"
	"github.com/gofiber/fiber/v2"
)

func main(){

	var container container.Container= container.Container{}

	container.Welcome(0)
	container.Init()
	container.Welcome(5)
	
	var balancer server.NotifyrBalancer = server.NotifyrBalancer{Container: &container,Fiber: fiber.New()}
	
	balancer.LoadMiddleWare()
	balancer.LoadRoute()
	balancer.Start()

	balancer.Shutdown()
}
