package server

import (
	"balancer/container"

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

func (balancer *NotifyrBalancer) Start(){}