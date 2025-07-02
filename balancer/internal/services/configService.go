package service

import (
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

var LOCAL_HOST = []string{"localhost", "127.0.0.1"}

func parseInt(envKey string,defaultVal int64) int64 {
	
	_port_start,exists := os.LookupEnv(envKey)
	if exists {
		port_start,err:= strconv.ParseInt(_port_start,10,64)
		if err!= nil{
			return defaultVal
		}else{
			return port_start
		}
	}else{
		return defaultVal
	}


}

func loadServer(envKey string, portStart int64) []string {
	_servers, exists := os.LookupEnv(envKey)
	if !exists {
		return nil
	}

	servers := []string{}
	mapServers := map[string]int64{}
	portCounter := portStart

	for _, s := range strings.Split(_servers, ",") {
		parsedURL, err := url.Parse(s)
		if err != nil {
			continue
		}

		hostname := parsedURL.Hostname()
		port := parsedURL.Port()

		// Increment port for every repetition of the hostname only if the port is not specified
		if port == "" {
			if _, exists := mapServers[hostname]; !exists {
				mapServers[hostname] = portCounter
			} else {
				mapServers[hostname]++
			}
			port = strconv.FormatInt(mapServers[hostname], 10)
		}

		parsedURL.Host = hostname + ":" + port
		finalURL := parsedURL.String()
		servers = append(servers, finalURL)
	}

	return servers
}

type ConfigService struct {
	URLS            []string
	API_KEY         string
	PORT_START      int64
	set bool
	addr string
	
}

func (config *ConfigService) Is_Set() bool {
	return config.set
}

func (config *ConfigService) Has_Apps()bool {
	return config.URLS != nil
}

func (config *ConfigService) Addr() string {

	return config.addr
}

func (config *ConfigService) LoadEnv() {
	err := godotenv.Load()
	if err != nil {
		log.Fatalf("Error loading .env file: %v", err)
		config.set = false
		return
	}

	api_key,exists := os.LookupEnv("API_KEY")
	if exists{
		config.API_KEY = api_key
	}

	addr,exist:= os.LookupEnv("ADDR")
	if exist {
		config.addr = addr
	}else{
		config.addr ="127.0.0.1:88"
	}

	config.PORT_START = parseInt("PORT_START",80)
	config.URLS = loadServer("NOTIFYR_URLS",config.PORT_START)
	config.set = true
}