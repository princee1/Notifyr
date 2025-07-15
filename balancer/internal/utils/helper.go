package utils

import (
	"fmt"
	"strings"

	"github.com/spaolacci/murmur3"
)

type CanSplit struct {
	split bool
}

func HashURL(url string) string {
	hash := murmur3.Sum64([]byte(url))
	return fmt.Sprintf("%x", hash)
}

func StartsWithAny(str string, prefixes []string) bool {
	for _, prefix := range prefixes {
		if strings.HasPrefix(str, prefix) {
			return true
		}
	}
	return false
}

func CopyOneLevelMap(original map[string]interface{}) map[string]interface{} {
	newMap := make(map[string]interface{})
	for k, v := range original {
		newMap[k] = v
	}
	return newMap
}
