package main

import (
	"balancer/container"
	"balancer/server"
	"github.com/gofiber/fiber/v2"
	"github.com/common-nighthawk/go-figure"
	"github.com/gookit/color"
)
import (
	"github.com/inancgumus/screen"
)

func Welcome() {
	screen.Clear()
	screen.MoveTopLeft()
	myFigure := figure.NewFigure("Notifyr Balancer", "slant", true)
	color.Green.Println(myFigure.String())
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
