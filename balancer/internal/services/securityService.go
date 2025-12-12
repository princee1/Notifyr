package service

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const TOKEN_NAME = "X-Ping-Pong-Token"
const EXCHANGE_TOKEN_FILE = "/run/secrets/balancer-exchange-token.txt"
const BALANCER_TOKEN_HEADER = "X-Balancer-Exchange-Token"

type SecurityService struct {
	ConfigService *ConfigService
	balancerExchangeToken string
}


func (security *SecurityService) LoadExchangeToken() {

	content,err:=os.ReadFile(security.ConfigService.exchangeTokenFilePath)
	if err != nil{
		log.Printf("Error while reading the exchange token file: %v",err)
		os.Exit(-1)
	}
	token := string(content)
	token = strings.TrimSpace(token)
	security.balancerExchangeToken = token
}

func (security *SecurityService) SignRequest() {

}

func (security *SecurityService) getPongWsPermission(url url.URL, name string, app *NotifyrApp) (string, error) {
	// Construct the permission URL
	permissionURL := fmt.Sprintf("%s/%s", url.String(), PERMISSION_ROUTE)
	ticker := time.NewTicker(RETRY_FREQ)
	client := &http.Client{}
	defer ticker.Stop()
	var resp *http.Response
	var err error
	var retry int = 0

	for {
		<-ticker.C
		
		req,err:= http.NewRequest("GET",permissionURL,nil)
		if err != nil {
			fmt.Println("Error creating request:", err)
			os.Exit(-1)
		}
		req.Header.Set(BALANCER_TOKEN_HEADER,security.balancerExchangeToken)

		resp, err = client.Do(req)	
		if err != nil {
			retry++
			if retry == int(MAX_RETRY) {
				return "", fmt.Errorf("failed to make GET request after %v retries: %v", MAX_RETRY, err)
			}

			log.Printf("Failed to make GET request (%s): Attempt %v / %v: Reason %v", name, retry, MAX_RETRY, err)
			continue
		} else {
			break

		}

	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("permission request failed for %s with status code: %d", name, resp.StatusCode)
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response body: %v", err)
	}

	err = json.Unmarshal(body, app)
	if err != nil {
		return "", fmt.Errorf("failed to parse response body into NotifyrApp: %v", err)
	}

	tokens, ok := resp.Header[TOKEN_NAME]
	if !ok || len(tokens) == 0 {
		return "", fmt.Errorf("failed to retrieve the permission token")
	}

	return tokens[0], nil
}
