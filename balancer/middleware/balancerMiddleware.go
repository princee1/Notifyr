package middleware

import (
	service "balancer/internal/services"
	"balancer/internal/utils"
	"fmt"
	"time"

	"github.com/gofiber/fiber/v2"
)

var SPLITABLE_ROUTES = []string{"/email/template/", "/email/custom/", "twilio/sms/ongoing/template/", "twilio/sms/ongoing/custom/", "twilio/call/ongoing/custom/", "twilio/sms/ongoing/twiml/", "twilio/sms/ongoing/template"}



type BaseMiddleware interface {
	Middleware(c *fiber.Ctx) error
}
type MetaDataMiddleware struct {
	SecurityService *service.SecurityService
}

func (metadata *MetaDataMiddleware) Middleware(c *fiber.Ctx) error {
	start := time.Now()
	err := c.Next()
	duration := time.Since(start)
	c.Set(utils.PROCESS_TIME_HEADER_NAME, fmt.Sprintf("%v (ms)", duration.Milliseconds()))
	fmt.Printf("\033[1;34mRequest:\033[0m Method=\033[1;32m%s\033[0m, URL=\033[1;32m%s\033[0m, IP=\033[1;32m%s\033[0m, ResponseCode=\033[1;31m%d\033[0m\n", c.Method(), c.OriginalURL(), c.IP(), c.Response().StatusCode())
	return err
}

type ActiveMiddleware struct {
	HealthService *service.HealthService
}

func (active *ActiveMiddleware) Middleware(c *fiber.Ctx) error {

	if active.HealthService.ActiveConnection() <= 0 {
		c.Response().SetStatusCode(fiber.StatusInternalServerError)
		return c.SendString("No Notifyr App At The moment, try again later")
	}
	return c.Next()
}

type SplitProxyMiddleware struct {
	ProxyService  *service.ProxyAgentService
	ConfigService *service.ConfigService
}

func (splitProxy *SplitProxyMiddleware) Middleware(c *fiber.Ctx) error {

	split := c.QueryBool("split", false)
	var canSplit bool = split
	if split {
		routeURL := c.OriginalURL()
		canSplit = utils.StartsWithAny(routeURL, SPLITABLE_ROUTES) && c.Method() == "POST"
	}

	c.Locals("canSplit", canSplit)
	return c.Next()
}

type ProxyMiddleware struct {
	ProxyService *service.ProxyAgentService
}

func (proxy *ProxyMiddleware) Middleware(c *fiber.Ctx) error {
	return proxy.ProxyService.ProxyRequest(c)
}
