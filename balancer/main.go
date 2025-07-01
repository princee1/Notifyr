package main

import (
	// "balancer/container"
	"balancer/server"
	"fmt"
	"github.com/gofiber/fiber/v2"
)



func main(){
	fmt.Println("load balancer")
	// var container container.Container= container.Container{}
	var balancer server.NotifyrBalancer = server.NotifyrBalancer{Fiber: fiber.New()}

	balancer.LoadMiddleWare()
	balancer.LoadRoute()
	balancer.Start()

}
