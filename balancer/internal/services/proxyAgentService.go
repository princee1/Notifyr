package service

import (
	"balancer/internal/algo"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	// "log"
	"net/http"
	"slices"
	"strings"
	"sync"

	"github.com/gofiber/fiber/v2"
)

type ProxyAgentService struct {
	HealthService *HealthService
	ConfigService *ConfigService
	currentAlgo   string
	algos         map[string]algo.Algo
}

func (proxy *ProxyAgentService) GetCurrentAlgo() algo.Algo {
	algo, ok := proxy.algos[proxy.currentAlgo]
	if ok {
		return algo
	}
	return nil
}

func (proxy *ProxyAgentService) SetAlgo(algoName string) error {
	if !slices.Contains(algo.ALGO_TYPE, algoName) {
		return fmt.Errorf("algorithm '%s' is not supported", algoName)
	}

	if _, exists := proxy.algos[algoName]; !exists {
		return fmt.Errorf("algorithm '%s' is not initialized", algoName)
	}

	proxy.currentAlgo = algoName
	return nil
}

func (proxy *ProxyAgentService) CreateAlgo() {

	// servers:= proxy.ConfigService.URLS
	// weight:= []uint64{1,1,1,1,1,1,1,1,1}
	proxy.algos = map[string]algo.Algo{}
	proxy.algos["random"] = &algo.RandomAlgo{}
	proxy.algos["round"] = &algo.RoundRobbinAlgo{}
	// proxy.algos["weight"] = &algo.WeightAlgo{}
	proxy.currentAlgo = "random"
}

func (proxy *ProxyAgentService) ProxyRequest(c *fiber.Ctx) error {
	var canSplit bool
	v, ok := c.Locals("canSplit").(bool)
	if !ok {
		canSplit = false
	} else {
		canSplit=v
	}

	var nextUrls []string = proxy.ChooseServer(canSplit)
	
	var wg sync.WaitGroup
	// var syncBody sync.Map;

	for _, nu := range nextUrls {
		nu = strings.Replace(c.OriginalURL(), proxy.ConfigService.addr, nu, -1)
		wg.Add(1)
		go func() {
			defer wg.Done()
			body := c.Body()
			proxy.CopyRequest(c, &body, nu)
		}()
	}
	wg.Wait()

	return c.Send(c.Body())
}

func (proxy *ProxyAgentService) SetContentIndex(c *fiber.Ctx) ([]byte, error) {
	var bodyMap map[string]interface{}

	if err := json.Unmarshal(c.Body(), &bodyMap); err != nil {
		return nil, err
	}

	if content, ok := bodyMap["content"].([]interface{}); ok {
		for i, item := range content {
			// Assert each item is a map and inject "_index"
			if itemMap, ok := item.(map[string]interface{}); ok {
				itemMap["index"] = i
			}
		}
	}
	modifiedBody, err := json.Marshal(bodyMap)
	if err != nil {
		return nil, err
	}
	return modifiedBody, nil
}

func (proxy *ProxyAgentService) sendRequest(c *fiber.Ctx, newBody *[]byte, nextUrl *string) (*http.Response, error) {
	reqBody := bytes.NewReader(c.Body())
	req, err := http.NewRequest(c.Method(), *nextUrl, reqBody)
	if err != nil {
		return nil, err
	}
	// Copy headers from the original request
	c.Request().Header.VisitAll(func(key, value []byte) {
		req.Header.Set(string(key), string(value))
	})

	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

func (proxy *ProxyAgentService) CopyRequest(c *fiber.Ctx, newBody *[]byte, nextUrl string) ([]byte,error) {
	// Create a new request with the same method and body
	var retry int

	for {
		resp, err := proxy.sendRequest(c, newBody, &nextUrl)
		if resp == nil {
			return nil,err
		}
		if resp.StatusCode == 503 {
			if retry < 5 {
				continue
			}
		}
		defer resp.Body.Close()
		// Copy response status, headers, and body back to the Fiber context
		c.Status(resp.StatusCode)

		for k, v := range resp.Header {
			for _, vv := range v {
				c.Set(k, vv)
			}
		}
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil,err
		}
		return body,nil
	}

}

func (proxy *ProxyAgentService) ChooseServer(split bool) []string {
	var servers = proxy.HealthService.ActiveServer()
	if split {
		return servers
	}
	var algorithm algo.Algo = proxy.GetCurrentAlgo()
	return []string{algorithm.Next(servers)}
}
