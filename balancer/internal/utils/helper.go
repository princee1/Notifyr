package utils

import (
	"fmt"
	"reflect"
	"slices"
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

func CopyOneLevelMap(original map[string]interface{},exclude []string) map[string]interface{} {
	newMap := make(map[string]interface{})
	for k, v := range original {
		if slices.Contains(exclude,k){
			continue
		}
		newMap[k] = v
	}
	return newMap
}


func IsSlice(value interface{}) bool {
	return reflect.TypeOf(value).Kind() == reflect.Slice
}