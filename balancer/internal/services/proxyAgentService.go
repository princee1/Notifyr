package service

type AppSpec struct {
	cpuCore uint;
	processCount uint;
	ram uint;
}

type NotifyrApp struct {
	id string;
	address string;
	port uint;
	roles []string;
	spec AppSpec;
}


type ProxyAgentService struct {
	
	NotifyrApps map[string]NotifyrApp;


}


func (proxy *ProxyAgentService) RegisterApps(){

}
