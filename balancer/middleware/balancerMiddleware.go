package middleware

import service "balancer/internal/services"


type BaseMiddleware interface {
	Middleware() 
}


type ProxyMiddleware struct {
	proxyService *service.ProxyAgentService
}

func (proxy *ProxyMiddleware) Middleware() {

}

type AccessMiddleware struct {
	securityService *service.SecurityService
}

func (proxy *AccessMiddleware) Middleware() {

}