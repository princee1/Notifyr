package server

import (
	"balancer/container"
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

}

func (balancer *NotifyrBalancer) Start() {

	return

	if !balancer.Container.GetHealthService().ConfigService.HasApps() {
		errMess := fmt.Sprintf("Failed to start server: %v", "No Notifyr App Created")
		log.Print(errMess)
		panic(errMess)
	}

	if balancer.Container.GetHealthService().ActiveConnection() <= 0 {
		errMess := fmt.Sprintf("Failed to start server: %v", "No Notifyr App are currently Connected")
		log.Print(errMess)
		panic(errMess)
	}

	if err := balancer.Fiber.Listen(balancer.Container.GetConfigService().Addr()); err != nil {
		log.Printf("Failed to start server: %v", err)
		panic(err)
	}
}
