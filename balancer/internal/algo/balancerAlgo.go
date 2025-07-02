package algo

import (
	"math/rand"
	"sync"
	"sync/atomic"
)

// TODO interface

type Algo interface {
	Next() string;
}

// ---------------------------------------        --------------------------------------------  //
type RoundRobbinAlgo struct {
	Servers []string;
	index uint64
	mu sync.Mutex
}

func (round *RoundRobbinAlgo) GetIndex() uint64{
	return round.index
}

func (round *RoundRobbinAlgo) reset() {
	round.mu.Lock()
	defer round.mu.Unlock()
	round.index = 0
}

func (round *RoundRobbinAlgo) Next() string {
	i := atomic.AddUint64(&round.index, 1)
	if i > 1_000_000_000_000_000 {
		round.reset()
	}
	return round.Servers[i%uint64(len(round.Servers))]
}

// ---------------------------------------        --------------------------------------------  //

type WeightAlgo struct {
	Servers []string
	Weight  []uint64
	index   uint64
	mu      sync.Mutex
	totalWeight uint64
}

func (weight *WeightAlgo) reset() {
	weight.mu.Lock()
	defer weight.mu.Unlock()
	weight.index = 0
}

func (weight *WeightAlgo) SetTotalWeight() {
	for _, w := range weight.Weight {
		weight.totalWeight += w
	}

}

func (weight *WeightAlgo) Next() string {
	i := atomic.AddUint64(&weight.index, 1)
	if i > 1_000_000_000_000_000 {
		weight.reset()
	}

	current := i % weight.totalWeight
	for idx, w := range weight.Weight {
		if current < w {
			return weight.Servers[idx]
		}
		current -= w
	}

	random := RandomAlgo{weight.Servers}
	return random.Next()
}

func (weight *WeightAlgo) GetIndex() uint64 {
	return weight.index
}

// ---------------------------------------        --------------------------------------------  //
type LeastConnectionAlgo struct {
	Servers []string;
	ptr int;
}

// ---------------------------------------        --------------------------------------------  //

type RandomAlgo struct {

	Servers []string
}

func (random *RandomAlgo) Next() string {
	i:=rand.Intn(len(random.Servers))
	return random.Servers[i]
}

// ---------------------------------------        --------------------------------------------  //

var ALGO_TYPE = []string{"random","round","weight"}