from __future__ import annotations
from typing import Tuple, List, Iterable

import numpy as np


def build_example_time_series(efficiency_direct_usage:float = 1.0, *a, **k) -> Tuple[Iterable[float | int], Iterable[float | int]]:

    energy_excess  = [8, 1, 2, 10, 4, 4, 1, 5, 6, 1, 5, 3, 7, 2, 7, 2, 1, 3, 5]
    energy_deficit = [8, 2, 2, 10, 4, 3, 2, 5, 6, 2, 6, 4, 5, 1, 7, 1, 2, 1, 4]

    power_generation = np.array([[e,0] for e in energy_excess]).flatten() / efficiency_direct_usage
    power_demand = np.array([[0, e] for e in energy_deficit]).flatten()
    return power_generation, power_demand

