package service

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
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

	// Make the GET request
	resp, err := http.Get(permissionURL)
	if err != nil {
		return "", fmt.Errorf("failed to make GET request: %v", err)
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