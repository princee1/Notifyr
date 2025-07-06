package service

import (
	"balancer/internal/algo"
	"fmt"
	"slices"
)

type ProxyAgentService struct {
	HealthService *HealthService
	ConfigService *ConfigService
	currentAlgo string
	algos       map[string]algo.Algo

}

func (proxy *ProxyAgentService) GetCurrentAlgo() algo.Algo{
	return proxy.algos[proxy.currentAlgo]
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
	
	servers:= proxy.ConfigService.URLS
	weight:= []uint64{1,1,1,1,1,1,1,1,1}
	proxy.algos = map[string]algo.Algo{}

	proxy.algos["random"] = &algo.RandomAlgo{Servers:servers}
	proxy.algos["round"] = &algo.RoundRobbinAlgo{Servers:servers}
	weightAlgo := algo.WeightAlgo{Servers: servers, Weight: weight}
	weightAlgo.SetTotalWeight()
	proxy.algos["weight"] =  &weightAlgo
	

	proxy.currentAlgo = "round"
}

func (proxy *ProxyAgentService) SplitRequest() {

}

func (proxy *ProxyAgentService) ProxyRequest() {

}

func (proxy *ProxyAgentService) ChooseServer()string {
	var algorithm algo.Algo = proxy.GetCurrentAlgo()
	server := algorithm.Next()
	return HashURL(server)
}
