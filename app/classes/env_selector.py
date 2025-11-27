import random
import math
from abc import ABC, abstractmethod
from typing import Dict, Literal


EnvSelection = Literal['route', 'worker', 'aps','routebkg']
ENVS=['route', 'worker', 'aps','routebkg']


class ProbabilisticEnvSelector(ABC):
    @abstractmethod
    def select(self, p1: float, p2: float, p3: float) -> EnvSelection:
        """
        Select one environment given system metrics.
        :param p1: Available workers
        :param p2: Ratio of functioning workers
        :param p3: Task cost
        :return: Selected environment
        """
        pass

    def compute_scores(self, p1: float, p2: float, p3: float) -> Dict[EnvSelection, float]:
        """
        Default scoring logic. Subclasses can override if needed.
        :return: Dictionary of environment scores
        """
        route_score = -p3                              # low cost → better for route
        worker_score = -abs(p3 - 5) + (3 * p2)         # medium cost & good p2 → better for worker
        background_score = p3 - (2 * p2)               # high cost or low p2 → better for background

        return {
            'route': route_score,
            'worker': worker_score,
            'routebkg': background_score,
            'aps': ...
        }


class RandomChoiceEnvSelector(ProbabilisticEnvSelector):
    def select(self, p1: float, p2: float, p3: float) -> EnvSelection:
        return random.choice(ENVS)


class SoftmaxEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, temp: float = 1.0):
        self.temperature = temp

    def select(self, p1: float, p2: float, p3: float) -> EnvSelection:
        scores = self.compute_scores(p1, p2, p3)
        keys = list(scores.keys())
        raw_scores = list(scores.values())

        exps = [math.exp(s / self.temperature) for s in raw_scores]
        total = sum(exps)
        probabilities = [e / total for e in exps]

        return random.choices(keys, weights=probabilities, k=1)[0]


class EpsilonGreedyEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, epsilon: float = 0.1):
        self.epsilon = epsilon

    def select(self, p1: float, p2: float, p3: float) -> EnvSelection:
        scores = self.compute_scores(p1, p2, p3)

        if random.random() < self.epsilon:
            return random.choice(list(scores.keys()))
        else:
            return max(scores.items(), key=lambda item: item[1])[0]


class BoltzmannEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, temp: float = 1.0):
        self.temperature = temp

    def select(self, p1: float, p2: float, p3: float) -> EnvSelection:
        scores = self.compute_scores(p1, p2, p3)
        keys = list(scores.keys())
        raw_scores = list(scores.values())
        max_score = max(raw_scores)

        exps = [math.exp((s - max_score) / self.temperature) for s in raw_scores]
        total = sum(exps)
        probabilities = [e / total for e in exps]

        return random.choices(keys, weights=probabilities, k=1)[0]



StrategyType = Literal['random', 'softmax', 'epsilon_greedy', 'boltzmann']

# Optional: Strategy factory
def get_selector(strategy: StrategyType, **kwargs) -> ProbabilisticEnvSelector:
    if strategy == 'random':
        return RandomChoiceEnvSelector()
    elif strategy == 'softmax':
        return SoftmaxEnvSelector(**kwargs)
    elif strategy == 'epsilon_greedy':
        return EpsilonGreedyEnvSelector(**kwargs)
    elif strategy == 'boltzmann':
        return BoltzmannEnvSelector(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
