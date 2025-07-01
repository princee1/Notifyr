package server

import (
	"github.com/gofiber/fiber/v2"
)

type NotifyrBalancer struct {
	Fiber *fiber.App
}


func (balancer *NotifyrBalancer) LoadRoute(){

}

func (balancer *NotifyrBalancer) LoadMiddleWare(){

}

func (balancer *NotifyrBalancer) Start(){}