package main

import (
	"balancer/container"
	"balancer/server"
	"fmt"
	"github.com/gofiber/fiber/v2"
)

func Welcome(){
	fmt.Println("")
}

func main(){

	Welcome()

	var container container.Container= container.Container{}
	container.Init()
	
	var balancer server.NotifyrBalancer = server.NotifyrBalancer{Container: &container,Fiber: fiber.New()}
	balancer.LoadMiddleWare()
	balancer.LoadRoute()
	balancer.Start()

}
