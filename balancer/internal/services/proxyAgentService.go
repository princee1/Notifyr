package service

import (
	"balancer/internal/algo"
	"balancer/internal/utils"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"slices"
	"sync"

	"github.com/gofiber/fiber/v2"
)

type NotifyrResp struct {
	header     *http.Header
	statusCode int
	body       *[]byte
}

var BODY_EXCLUDE = []string{"content"}
const X_REQUEST_ID_KEY = "x_request_id"

type ProxyAgentService struct {
	HealthService *HealthService
	ConfigService *ConfigService
	currentAlgo   string
	algos         map[string]algo.Algo
}

func (proxy *ProxyAgentService) GetCurrentAlgo() algo.Algo {
	algo, ok := proxy.algos[proxy.currentAlgo]
	if ok {
		return algo
	}
	return nil
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

	// servers:= proxy.ConfigService.URLS
	// weight:= []uint64{1,1,1,1,1,1,1,1,1}
	proxy.algos = map[string]algo.Algo{}
	proxy.algos["random"] = &algo.RandomAlgo{}
	proxy.algos["round"] = &algo.RoundRobbinAlgo{}
	// proxy.algos["weight"] = &algo.WeightAlgo{}
	proxy.currentAlgo = "random"
}

func (proxy *ProxyAgentService) getCanSplit(c *fiber.Ctx) bool {

	v, ok := c.Locals("canSplit").(bool)
	if !ok {
		return false
	} else {
		return v
	}
}

func (proxy *ProxyAgentService) ProxyRequest(c *fiber.Ctx) error {
	var canSplit bool = proxy.getCanSplit(c)
	var nextUrls []string = proxy.ChooseServer(canSplit)
	var wg sync.WaitGroup
	var syncResp sync.Map = sync.Map{}
	var syncBodies [][]byte

	if canSplit {
		body, err := proxy.SplitRequest(c, len((nextUrls)))
		if err != nil {
			return c.Status(500).SendString(fmt.Sprintf("%v", err))
		}
		syncBodies = *body

	} else {
		syncBodies = [][]byte{
			c.Body(),
		}
	}

	for index, nu := range nextUrls {
		nu += c.OriginalURL()
		wg.Add(1)
		go func() {
			defer wg.Done()
			body := syncBodies[index]
			proxy.CopyRequest(c, &body, nu, index, &syncResp)
		}()
	}
	wg.Wait()


	return proxy.MergeRequest(c,&syncResp)
}

func (proxy *ProxyAgentService) SplitRequest(c *fiber.Ctx, length int) (*[][]byte, error) {
	var bodyMap map[string]interface{}
	var copyBodies []map[string]interface{};

	if err := json.Unmarshal(c.Body(), &bodyMap); err != nil {
		return nil, err
	}

	if content, ok := bodyMap["content"].([]interface{}); ok {
		
		if !utils.IsSlice(content){
			return nil,fmt.Errorf("cannot split a non list of content",)
		}

		if len(content) < length{
			return nil, fmt.Errorf("the length of the content is lower than the number of underlying apps, toggle split to False")
		}

		for i := 0; i < length; i++ {
			b:=utils.CopyOneLevelMap(bodyMap, BODY_EXCLUDE)
			copyBodies = append(copyBodies, b)
		}

		var a int
		var b int
		var index int
		var c_len = len(content)

		for i, item := range content {
			n_i:= i+1
			if itemMap, ok := item.(map[string]interface{}); ok {
				itemMap["index"] = i
			}

			if n_i % length == 1{
				a = i
			}

			if n_i % length == 0 || (c_len-n_i <length){ 
				b=i
				copyBodies[index]["content"]= content[a:b]
				index++
			}

		}
	} else {
		return nil,fmt.Errorf("no content specified")
	}

	var modifiedBody [][]byte = [][]byte{}

	for i:=0;i<length;i++{

		body,err := json.Marshal(copyBodies[i])
		if err != nil {
			return nil, err
		}
		modifiedBody = append(modifiedBody,body)
	}
	
	return &modifiedBody, nil
}

func (proxy *ProxyAgentService) sendRequest(c *fiber.Ctx, newBody *[]byte, nextUrl *string) (*http.Response, error) {
	reqBody := bytes.NewReader(*newBody)
	req, err := http.NewRequest(c.Method(), *nextUrl, reqBody)
	if err != nil {
		return nil, err
	}
	// Copy headers from the original request
	c.Request().Header.VisitAll(func(key, value []byte) {
		req.Header.Set(string(key), string(value))
	})

	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

func (proxy *ProxyAgentService) CopyRequest(c *fiber.Ctx, newBody *[]byte, nextUrl string, index int, syncResp *sync.Map) error {
	// Create a new request with the same method and body
	var retry int

	for {
		resp, err := proxy.sendRequest(c, newBody, &nextUrl)
		if resp == nil {
			return err
		}
		if resp.StatusCode == 503 {
			if retry < 5 {
				continue
			}
		}
		defer resp.Body.Close()
		// Copy response status, headers, and body back to the Fiber context

		bodyBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return err
		}

		syncResp.Store(index, NotifyrResp{
			header:     &resp.Header,
			statusCode: resp.StatusCode,
			body:       &bodyBytes,
		})
		return nil
	}
}

func (proxy *ProxyAgentService) MergeRequest(c *fiber.Ctx, syncResp *sync.Map) error {
	mergedResults := []interface{}{}
    mergedErrors := map[string]interface{}{}
	mergedMeta :=map[string]interface{}{}

    requestIDsSet := []string{}
	var _err error=nil;
	_is_meta_set := false

	syncResp.Range(func(key, value any) bool {
		
	
		p, ok := value.(NotifyrResp)
		if !ok{
			return false
		}

		if p.statusCode != 201  && p.statusCode!=200 {
			return false
		}
		var  payload map[string]interface{}
		if err := json.Unmarshal(*p.body, &payload); err != nil {
			_err =err
			return false
		}

		if meta,ok:= payload["meta"].(map[string]interface{});ok {

			if !_is_meta_set{

				mergedMeta = utils.CopyOneLevelMap(meta,[]string{X_REQUEST_ID_KEY})
				requestIDsSet = append(requestIDsSet, fmt.Sprintf("%v",meta[X_REQUEST_ID_KEY]))
				_is_meta_set = true
			}else{
				requestIDsSet = append(requestIDsSet,fmt.Sprintf("%v",meta[X_REQUEST_ID_KEY]))
			}
		}

        if results, ok := payload["results"].([]interface{}); ok {
            mergedResults = append(mergedResults, results...)
        }

        if errors, ok := payload["errors"].(map[string]interface{}); ok {
            for k, v := range errors {
                mergedErrors[k] = v
            }
        }
		return true	
	})
	
	mergedMeta[X_REQUEST_ID_KEY]= requestIDsSet

	return _err
}

func (proxy *ProxyAgentService) ChooseServer(split bool) []string {
	var servers = proxy.HealthService.ActiveServer()
	if split {
		return servers
	}
	var algorithm algo.Algo = proxy.GetCurrentAlgo()
	return []string{algorithm.Next(servers)}
}
