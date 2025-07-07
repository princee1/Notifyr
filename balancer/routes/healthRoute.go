package route

import "balancer/internal/services"

type HealthRoute struct {
	HealthService *service.HealthService
	ProxyAgentService *service.ProxyAgentService
}

