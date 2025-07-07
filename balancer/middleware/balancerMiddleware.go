package middleware

import (
	service "balancer/internal/services"
	"fmt"
	"time"

	"github.com/gofiber/fiber/v2"
)


const PROCESS_TIME_HEADER_NAME = "X-Balancer-Process-Time"


type BaseMiddleware interface {
	Middleware(c *fiber.Ctx)  error
}
type MetaDataMiddleware struct {
	SecurityService *service.SecurityService
}

func (metadata *MetaDataMiddleware) Middleware(c *fiber.Ctx) error{
	start:= time.Now()
	err := c.Next()
	duration := time.Since(start)
	c.Set(PROCESS_TIME_HEADER_NAME,fmt.Sprintf("%v",duration))
	return err
}

type ProxyMiddleware struct {
	ProxyService *service.ProxyAgentService
}

func (proxy *ProxyMiddleware) Middleware(c *fiber.Ctx) error{

	return nil
}

type AccessMiddleware struct {
	SecurityService *service.SecurityService
}

func (access *AccessMiddleware) Middleware(c *fiber.Ctx) {

}