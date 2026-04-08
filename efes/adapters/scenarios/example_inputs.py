from __future__ import annotations
from typing import Tuple,  Iterable

import numpy as np


def build_example_time_series() -> Tuple[Iterable[float | int], Iterable[float | int]]:
    power_generation = np.array([2, 3, 2, 4, 3, 1, 0, 0, 2, 5, 6, 2, 1, 0, 1, 2, 3, 2, 0, 0, 4, 4, 4, 2])
    power_demand = np.array([1, 4, 1, 2, 1, 2, 4, 5, 0, 1, 3, 1, 2, 2, 1, 1, 2, 3, 4, 5, 2, 1, 5, 1])
    return power_generation, power_demand
