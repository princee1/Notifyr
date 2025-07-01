package container

import service "balancer/internal/services"


type Container struct {
	HealthService *service.HealthService
	ConfigService *service.ConfigService
	SecurityService *service.SecurityService
	ProxyAgentService *service.ProxyAgentService
}


func (container *Container) Init(){
	container.ConfigService = &service.ConfigService{}
	container.SecurityService = &service.SecurityService{ConfigService: container.ConfigService}
	container.ProxyAgentService = &service.ProxyAgentService{}
	container.HealthService= &service.HealthService{ProxyService: container.ProxyAgentService,SecurityService: container.SecurityService }

	container.ConfigService.LoadEnv()
	container.HealthService.CreatePPClient()
	container.HealthService.StartConnection()
}
