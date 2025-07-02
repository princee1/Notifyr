package service

import (
	"balancer/internal/algo"
	"fmt"
	"slices"
)


type AppSpec struct {
	cpuCore      uint
	processCount uint
	ram          uint
	weight       float64
}

type NotifyrApp struct {
	id         string
	instanceId string
	address    string
	port       uint
	roles      []string
	spec       AppSpec
	active     bool
}


type ProxyAgentService struct {
	NotifyrApps map[string]NotifyrApp
	algos       map[string]algo.Algo
	ConfigService *ConfigService

	currentAlgo string

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

	proxy.algos["random"] = &algo.RandomAlgo{Servers:servers}
	proxy.algos["round"] = &algo.RoundRobbinAlgo{Servers:servers}
	proxy.algos["weight"] = &algo.WeightAlgo{Servers: servers, Weight: weight}

	proxy.currentAlgo = "round"
}

func (proxy *ProxyAgentService) RegisterApps() {

}

func (proxy *ProxyAgentService) ToggleActiveApps() {

}

func (proxy *ProxyAgentService) SplitRequest() {

}

func (proxy *ProxyAgentService) ProxyRequest() {

}

func (proxy *ProxyAgentService) ChooseServer() {

}
