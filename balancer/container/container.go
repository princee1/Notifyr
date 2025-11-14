package container

import (
	service "balancer/internal/services"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/common-nighthawk/go-figure"
	"github.com/gookit/color"
	"github.com/inancgumus/screen"
)

const SECOND int64 = 1_000_000_000

type Container struct {
	healthService     *service.HealthService
	configService     *service.ConfigService
	securityService   *service.SecurityService
	proxyAgentService *service.ProxyAgentService
	wg                *sync.WaitGroup
	Quit              *chan os.Signal
}

func (container *Container) Init() {

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM,syscall.SIGINT)

	container.Quit = &quit

	container.configService = &service.ConfigService{}
	container.securityService = &service.SecurityService{ConfigService: container.configService}
	container.healthService = &service.HealthService{ConfigService: container.configService, SecurityService: container.securityService}
	container.proxyAgentService = &service.ProxyAgentService{HealthService: container.healthService, ConfigService: container.configService}

	container.configService.LoadEnv()
	container.proxyAgentService.CreateAlgo()
	container.healthService.WFInitChan()
	container.wg = container.healthService.InitPingPongConnection(container.proxyAgentService)
}

func (container *Container) WaitWS() {
	container.wg.Wait()
}

func (container *Container) GetHealthService() *service.HealthService {
	return container.healthService
}

func (container *Container) GetConfigService() *service.ConfigService {
	return container.configService
}

func (container *Container) GetSecurityService() *service.SecurityService {
	return container.securityService
}

func (container *Container) GetProxyAgentService() *service.ProxyAgentService {
	return container.proxyAgentService
}

func (container *Container) Welcome(sleep int) {
	time.Sleep(time.Duration(sleep * int(SECOND)))
	screen.Clear()
	screen.MoveTopLeft()
	myFigure := figure.NewFigure("Notifyr Balancer", "slant", true)
	color.Green.Println(myFigure.String())
}
