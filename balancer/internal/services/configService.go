package service

import (
	"fmt"
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

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
			s = fmt.Sprintf("%v://%v:%v", base_url.Scheme,base_url.Hostname(), port)
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

type ConfigService struct {
	URLS           []string
	api_key        string
	PORT_START     int64
	set            bool
	addr           string
	port_increment uint
	app_count      int64
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
		log.Fatalf("Error loading .env file: %v", err)
		config.set = false
		return
	}

	api_key, exists := os.LookupEnv("API_KEY")
	if exists {
		config.api_key = api_key
	}

	addr, exist := os.LookupEnv("ADDR")
	if exist {
		config.addr = addr
	} else {
		config.addr = "127.0.0.1:88"
	}

	config.PORT_START = parseInt("PORT_START", 8080)

	config.port_increment = uint(parseInt("PORT_INCREMENT", 1))

	config.app_count = parseInt("APP_COUNT", -1)

	config.URLS = loadServer("NOTIFYR_URLS", config.PORT_START, config.app_count, int64(config.port_increment))
	config.set = true
}

func (config *ConfigService) GetAppCount() int64 {
	return config.app_count
}
