package server

import (
	"balancer/container"
	"log"

	"github.com/gofiber/fiber/v2"
)

type NotifyrBalancer struct {
	Container *container.Container
	Fiber *fiber.App
}


func (balancer *NotifyrBalancer) LoadRoute(){

}

func (balancer *NotifyrBalancer) LoadMiddleWare(){

}

func (balancer *NotifyrBalancer) Start() {
	if err := balancer.Fiber.Listen(balancer.Container.GetConfigService().Addr()); err != nil {
		log.Printf("Failed to start server: %v", err)
		panic(err)
	}
}