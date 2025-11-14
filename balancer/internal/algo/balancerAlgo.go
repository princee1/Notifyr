package algo

import (
	"math/rand"
	"sync"
	"sync/atomic"
)

// TODO interface

var ALGO_TYPE = []string{"random","round","weight"}

type Algo interface {
	Next([]string) string;
	GetIndex() uint64;
}

// ---------------------------------------        --------------------------------------------  //
type RoundRobbinAlgo struct {
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

func (round *RoundRobbinAlgo) Next(Servers []string) string {
	i := atomic.AddUint64(&round.index, 1)
	if i > 1_000_000_000_000_000 {
		round.reset()
	}
	return Servers[i%uint64(len(Servers))]
}

// ---------------------------------------        --------------------------------------------  //

type WeightAlgo struct {
	index   uint64
	mu      sync.Mutex
}

func (weight *WeightAlgo) reset() {
	weight.mu.Lock()
	defer weight.mu.Unlock()
	weight.index = 0
}

func (weight *WeightAlgo) setTotalWeight(Servers []string,Weight []uint64) uint64{
	var totalWeight uint64;
	if len(Servers) != len(Weight){
	}
	for _, w := range Weight {
		totalWeight += w
	}
	return totalWeight

}

func (weight *WeightAlgo) Next(Servers []string) string {
	Weight := []uint64{3,4}
	totalWeight:= weight.setTotalWeight(Servers,Weight)

	i := atomic.AddUint64(&weight.index, 1)
	if i > 1_000_000_000_000_000 {
		weight.reset()
	}

	current := i % totalWeight
	for idx, w := range Weight {
		if current < w {
			return Servers[idx]
		}
		current -= w
	}

	random := RandomAlgo{Servers}
	return random.Next(Servers)
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

func (random *RandomAlgo) Next(Servers []string) string {
	i:=rand.Intn(len(Servers))
	return Servers[i]
}

func (random *RandomAlgo) GetIndex() uint64{
	return 0
}

// ---------------------------------------        --------------------------------------------  //
