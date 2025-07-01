package container

import service "balancer/internal/services"


type Container struct {
	healthService *service.HealthService
	configService *service.ConfigService
	securityService *service.SecurityService
	proxyAgentService *service.ProxyAgentService
}


func (container *Container) Init(){
	container.configService = &service.ConfigService{}
	container.securityService = &service.SecurityService{ConfigService: container.configService}
	container.proxyAgentService = &service.ProxyAgentService{}
	container.healthService= &service.HealthService{ProxyService: container.proxyAgentService,SecurityService: container.securityService }

	container.configService.LoadEnv()
	container.healthService.CreatePPClient()
	container.healthService.StartConnection()
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
