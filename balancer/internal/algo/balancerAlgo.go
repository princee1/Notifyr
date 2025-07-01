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
	servers []string
	weight []uint16
	
}

// ---------------------------------------        --------------------------------------------  //
type LeastConnectionAlgo struct {
	servers []string;
	ptr int;

}

// ---------------------------------------        --------------------------------------------  //

type RandomAlgo struct {

	servers []string
}

func (random *RandomAlgo) Next() string {
	i:=rand.Intn(len(random.servers))
	return random.servers[i]
}

// ---------------------------------------        --------------------------------------------  //
