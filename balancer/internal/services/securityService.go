package service

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"time"
)

const TOKEN_NAME = "X-Ping-Pong-Token"

type SecurityService struct {
	ConfigService *ConfigService
}

func (security *SecurityService) SignRequest() {

}

func (security *SecurityService) VerifyApiKey(key string) bool {

	return true
}

func (security *SecurityService) getPongWsPermission(url url.URL, name string, app *NotifyrApp) (string, error) {
	// Construct the permission URL
	permissionURL := fmt.Sprintf("%s/%s", url.String(), PERMISSION_ROUTE)

	ticker := time.NewTicker(RETRY_FREQ)
	defer ticker.Stop()
	var resp *http.Response
	var err error
	var retry int = 0

	for {
		<-ticker.C

		resp, err = http.Get(permissionURL)
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
