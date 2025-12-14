package service

import (
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

type Scaling struct {
	App int8 `json:"app"`
	Worker int8 `json:"worker"`
	Balancer int8 `json:"balancer"`
} 

type DeployConfig struct {
	Scaling Scaling `json:"scaling"`
	Version string `json:"version"`	
}

var LOCAL_HOST = []string{"localhost", "127.0.0.1"}

func parseInt(envKey string, defaultVal int64) int64 {

	_port_start, exists := os.LookupEnv(envKey)
	if exists {
		port_start, err := strconv.ParseInt(_port_start, 10, 64)
		if err != nil {
			return defaultVal
		} else {
			return port_start
		}
	} else {
		return defaultVal
	}

}

func loadServer(envKey string, portStart int64, app_count int64, increment int64) []string {
	_servers, exists := os.LookupEnv(envKey)
	if !exists {
		return []string{}
	}

	servers := []string{}
	mapServers := map[string]int64{}
	portCounter := portStart

	config_server := strings.Split(_servers, ",")

	if app_count > 0 && len(config_server) == 1 {
		base_url, err := url.Parse(config_server[0])
		if err != nil {
			return []string{}
		}
		for i := 0; i < int(app_count); i++ {
			var s string
			var _port_start int64
			if base_url.Port() != "" {
				_port_start, err = strconv.ParseInt(base_url.Port(), 10, 64)
				if err != nil {
					_port_start = portStart
				}
			} else {
				_port_start = portStart
			}
			port := int(_port_start) + (i * int(increment))
			s = fmt.Sprintf("%v://%v:%v", base_url.Scheme, base_url.Hostname(), port)
			servers = append(servers, s)
		}

		return servers
	}

	for _, s := range config_server {
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
				mapServers[hostname] += increment
			}
			port = strconv.FormatInt(mapServers[hostname], 10)
		}

		parsedURL.Host = hostname + ":" + port
		finalURL := parsedURL.String()
		servers = append(servers, finalURL)
	}

	return servers
}

func generate_server_url(filepath string,port int) ([]string, error) {
	content,err :=os.ReadFile(filepath)
	if err!=nil {
		return nil,err
	}
	var deploy DeployConfig
	err = json.Unmarshal(content, &deploy)

	if err != nil{
		return nil,err
	}
	servers:= []string {}

	var i int8
	for i = 0; i < deploy.Scaling.App; i++ {
		server := fmt.Sprintf("notifyr-app-%v",i+1)
		url := fmt.Sprintf("http://%v:%v",server, port)
		servers = append(servers,url)
	} 
	
	return servers,nil
}

type ConfigService struct {
	URLS         []string
	NOTIFYR_PORT int64
	set          bool
	addr         string
	exchangeTokenFilePath string
}

func (config *ConfigService) IsSet() bool {
	return config.set
}

func (config *ConfigService) HasApps() bool {
	return len(config.URLS) > 0
}

func (config *ConfigService) Addr() string {
	return config.addr
}

func (config *ConfigService) LoadEnv() {

	err := godotenv.Load()
	if err != nil {
		log.Printf("Error loading .env file: %v", err)
	}

	addr, exist := os.LookupEnv("ADDR")
	if exist {
		config.addr = addr
	} else {
		config.addr = "127.0.0.1:88"
	}

	deploy_file_path ,exist := os.LookupEnv("DEPLOY_FILE_PATH")
	if ! exist {
		log.Printf("No file deploy filepath was given: %v", err)
		os.Exit(-1)
	}

	config.NOTIFYR_PORT = parseInt("NOTIFYR_PORT", 8080)

	urls, err := generate_server_url(deploy_file_path,int(config.NOTIFYR_PORT))
	if err != nil {
		log.Printf("No file deploy filepath was given: %v", err)
		os.Exit(-1)
	}

	exchange_token_file, exist := os.LookupEnv("EXCHANGE_TOKEN_FILE_PATH")
	if  !exist {
		log.Printf("No exchange token filepath was given: %v", err)
		os.Exit(-1)
	}

	config.exchangeTokenFilePath = exchange_token_file

	config.URLS = urls
	config.set = true
}
