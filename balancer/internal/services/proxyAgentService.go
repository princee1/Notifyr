package service

type AppSpec struct {
	cpuCore uint;
	processCount uint;
	ram uint;
	weight float64;
}

type NotifyrApp struct {
	id string;
	instanceId string;
	address string;
	port uint;
	roles []string;
	spec AppSpec;
	active bool
}


type ProxyAgentService struct {
	
	NotifyrApps map[string]NotifyrApp;
}


func (proxy *ProxyAgentService) RegisterApps(){

}

func (proxy *ProxyAgentService) ToggleActiveApps(){

}

func (proxy *ProxyAgentService) SplitRequest(){

}

func (proxy *ProxyAgentService) ProxyRequest(){

}

func (proxy *ProxyAgentService) ChooseServer() {

}
