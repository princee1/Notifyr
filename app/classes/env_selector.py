import random
import math
from abc import ABC, abstractmethod
from typing import Dict, Literal, List, Optional

EnvSelection = Literal['route', 'worker', 'aps', 'routebkg']
ENVS: List[EnvSelection] = ['route', 'worker', 'aps', 'routebkg']
DEFAULT_MASK = [1, 1, 1, 1]


# ======================================================================
# =============== P-VALUE COMPUTATION ==================================
# ======================================================================
def compute_p_values(
    celery_alive_workers: int,
    celery_expected_workers: int,
    task_weight: float
):
    """ Compute normalized p1, p2, p3. """

    p1 = max(celery_alive_workers, 0)
    p2 = p1 / celery_expected_workers if celery_expected_workers > 0 else 0
    p3 = float(task_weight)

    return p1, p2, p3


# ======================================================================
# =============== BASE CLASS ===========================================
# ======================================================================
class ProbabilisticEnvSelector(ABC):

    def __init__(
        self,
        *,
        celery_broker: Literal["redis", "rabbitmq"] = "rabbitmq",
        redis_long_task_threshold: float = 5.0
    ):
        """
        celery_broker:
            - "rabbitmq": safe for long-running tasks → prefer worker
            - "redis": dangerous for long tasks → prefer APS for high p3

        redis_long_task_threshold:
            weight above which redis becomes dangerous
        """
        self.broker = celery_broker
        self.redis_threshold = redis_long_task_threshold

    @abstractmethod
    def select(self, p1: float, p2: float, p3: float,
               mask: List[int] = DEFAULT_MASK) -> EnvSelection:
        pass

    # ------------------------------------------------------------------
    # Reliability-aware scoring
    # ------------------------------------------------------------------
    def compute_scores(self, p1: float, p2: float, p3: float) -> Dict[EnvSelection, float]:

        # ---------------------------------------------------------------
        # Base scoring (unchanged from earlier update)
        # ---------------------------------------------------------------
        route_score = -p3 * 1.4 + (1 - p2) * 0.2

        worker_score = (
            (2 * p1) +
            (4 * p2) -
            abs(p3 - 5)
        )

        background_score = -abs(p3 - 3) + (1 - p2)

        aps_score = (
            (p3 * 1.6) +        # APS is good for heavy tasks
            (1 - p1) * 2 +      # Celery sparse
            (1 - p2) * 2.5      # Celery unhealthy
        )

        # ---------------------------------------------------------------
        # Redis vs RabbitMQ scoring adjustments
        # ---------------------------------------------------------------

        if self.broker == "redis":
            # Redis is bad for long tasks – push away from worker
            if p3 >= self.redis_threshold:
                worker_score -= p3 * 1.5       # punish worker
                aps_score += p3 * 1.0          # reward APS

                # Background becomes mildly better than worker for Redis
                background_score += 0.5

        elif self.broker == "rabbitmq":
            # RabbitMQ is *strong* for long running tasks
            worker_score += p3 * 1.2
            aps_score -= 0.6 * p3  # less APS needed when Rabbit is stable

        return {
            'route': route_score,
            'worker': worker_score,
            'aps': aps_score,
            'routebkg': background_score
        }

    # ------------------------------------------------------------------
    # Apply mask (ignore disabled envs)
    # ------------------------------------------------------------------
    def apply_mask(self, scores: Dict[EnvSelection, float], mask: List[int]):
        return {
            env: score
            for env, score in scores.items()
            if mask[ENVS.index(env)] == 1
        }


# ======================================================================
# =============== STRATEGIES ===========================================
# ======================================================================

class RandomChoiceEnvSelector(ProbabilisticEnvSelector):
    def select(self, p1, p2, p3, mask=DEFAULT_MASK):
        allowed = [env for env, m in zip(ENVS, mask) if m == 1]
        return random.choice(allowed)


class SoftmaxEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, temp=1.0, **kwargs):
        super().__init__(**kwargs)
        self.temperature = temp

    def select(self, p1, p2, p3, mask=DEFAULT_MASK):
        scores = self.apply_mask(self.compute_scores(p1, p2, p3), mask)
        keys = list(scores.keys())
        raw_scores = list(scores.values())

        exps = [math.exp(s / self.temperature) for s in raw_scores]
        total = sum(exps)
        return random.choices(keys, weights=[e/total for e in exps])[0]


class EpsilonGreedyEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, epsilon=0.1, **kwargs):
        super().__init__(**kwargs)
        self.epsilon = epsilon

    def select(self, p1, p2, p3, mask=DEFAULT_MASK):
        scores = self.apply_mask(self.compute_scores(p1, p2, p3), mask)

        if random.random() < self.epsilon:
            return random.choice(list(scores.keys()))
        else:
            return max(scores.items(), key=lambda x: x[1])[0]


class BoltzmannEnvSelector(ProbabilisticEnvSelector):
    def __init__(self, temp=1.0, **kwargs):
        super().__init__(**kwargs)
        self.temperature = temp

    def select(self, p1, p2, p3, mask=DEFAULT_MASK):
        scores = self.apply_mask(self.compute_scores(p1, p2, p3), mask)

        keys = list(scores.keys())
        raw_scores = list(scores.values())

        max_score = max(raw_scores)
        exps = [math.exp((s - max_score) / self.temperature) for s in raw_scores]
        total = sum(exps)

        return random.choices(keys, weights=[e/total for e in exps])[0]


# ======================================================================
# =============== FACTORY ==============================================
# ======================================================================
StrategyType = Literal['random', 'softmax', 'epsilon_greedy', 'boltzmann']


def get_selector(strategy: StrategyType, **kwargs) -> ProbabilisticEnvSelector:
    if strategy == 'random':
        return RandomChoiceEnvSelector(**kwargs)
    elif strategy == 'softmax':
        return SoftmaxEnvSelector(**kwargs)
    elif strategy == 'epsilon_greedy':
        return EpsilonGreedyEnvSelector(**kwargs)
    elif strategy == 'boltzmann':
        return BoltzmannEnvSelector(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
