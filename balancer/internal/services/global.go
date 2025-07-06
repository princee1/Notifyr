package service

import (
    "github.com/spaolacci/murmur3"
    "fmt"
)

func HashURL(url string) string {
    hash := murmur3.Sum64([]byte(url))
    return fmt.Sprintf("%x", hash)
}
