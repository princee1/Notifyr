package route

import service "balancer/internal/services"

type StatsRoute struct {
	ProxyAgentService *service.ProxyAgentService
	Route string
}
