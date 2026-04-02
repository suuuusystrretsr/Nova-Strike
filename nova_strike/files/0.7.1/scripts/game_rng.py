import random
import time
from typing import Any, Sequence


class GameRNG:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = 0
        self._random = random.Random()
        self.reset(seed)

    def reset(self, seed: int | None = None) -> int:
        if seed is None:
            seed = (time.time_ns() ^ random.SystemRandom().randrange(1, 2**31 - 1)) & 0x7FFFFFFF
        self.seed = int(seed)
        self._random.seed(self.seed)
        return self.seed

    def random(self) -> float:
        return self._random.random()

    def uniform(self, a: float, b: float) -> float:
        return self._random.uniform(a, b)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def randrange(self, *args) -> int:
        return self._random.randrange(*args)

    def choice(self, seq: Sequence[Any]) -> Any:
        return self._random.choice(seq)

    def shuffle(self, seq: list) -> None:
        self._random.shuffle(seq)

