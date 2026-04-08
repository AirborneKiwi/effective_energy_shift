from __future__ import annotations
from typing import Tuple,  Iterable

import random
import numpy as np


def build_neg_corr(n_phase_pairs:int, efficiency_direct_usage:float = 1.0, *a, **k) -> Tuple[Iterable[float | int], Iterable[float | int]]:
    energy_excess = np.linspace(1.0,1000.0, int(n_phase_pairs))
    energy_deficit = energy_excess[-1::-1]
    power_generation = np.array([[e, 0] for e in energy_excess]).flatten() / efficiency_direct_usage
    power_demand = np.array([[0, e] for e in energy_deficit]).flatten()
    return power_generation, power_demand


def build_random_time_series(
    n_phase_pairs: int,
    n_time_steps: int | None = None,
    ratio_dem_to_gen:float = 1.0,
    efficiency_direct_usage:float = 1.0,
    seed: int | None = None,
    normalize_power_peak: bool = False,
    normalize_energy: bool = True,
):
    if normalize_power_peak and normalize_energy:
        raise AttributeError(f'You cannot normalize to both: energy and power peak.')

    (
        power_generation,
        power_demand,
        power_residual_generation,
        power_residual_generation_raw,
        offset_profile,
        ratio_gen_share,
    ) = create_random_time_series(
        n_time_steps=n_time_steps,
        n_phase_pairs=n_phase_pairs,
        ratio_dem_to_gen=ratio_dem_to_gen*efficiency_direct_usage,
        seed=42,
    )

    if normalize_power_peak:
        power_max = max(max(power_generation), max(power_demand))
        power_generation = np.array(power_generation) / power_max
        power_demand = np.array(power_demand) / power_max

    if normalize_energy:
        energy_max = max(sum(power_generation), sum(power_demand))
        power_generation = np.array(power_generation) / energy_max
        power_demand = np.array(power_demand) / energy_max

    return power_generation, power_demand


def random_bumpy_series_interp(n, seed=None, sharpness=1.5, knots=8, noise_level=0.2):
    if n < 2:
        raise ValueError("n must be at least 2")
    if knots < 2:
        raise ValueError("knots must be at least 2")

    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, n)

    envelope = np.sin(np.pi * t) ** sharpness

    tk = np.linspace(0, 1, knots)
    vk = rng.uniform(0.3, 1.2, size=knots)

    random_part = np.interp(t, tk, vk) + rng.uniform(0, noise_level, size=n)
    y = envelope * random_part
    y[0] = 0.0
    y[-1] = 0.0

    if n > 2:
        y[1:-1] = np.maximum(y[1:-1], 1e-12)

    return y


def rebalance_residual_for_target(C, ratio_dem_to_gen, safety=0.95):
    """
    Deterministically rebalance the raw residual so the target ratio becomes feasible.

    For k < 1, feasibility of a nonnegative split requires:
        sum(neg) / sum(pos) <= k
    We enforce a slightly stricter condition:
        sum(neg) / sum(pos) = safety * k

    For k > 1, feasibility requires:
        sum(neg) / sum(pos) >= k
    We enforce:
        sum(neg) / sum(pos) = k / safety
    """
    C = np.asarray(C, dtype=float)
    k = float(ratio_dem_to_gen)

    if k <= 0:
        raise ValueError("ratio_dem_to_gen must be > 0")
    if not (0 < safety < 1):
        raise ValueError("safety must be in (0, 1)")

    pos = np.maximum(C, 0.0)
    neg = np.maximum(-C, 0.0)

    P = pos.sum()
    N = neg.sum()

    if P == 0 and N == 0:
        return C.copy()

    if P == 0:
        raise ValueError("Raw residual has no positive values.")
    if N == 0:
        if k < 1:
            return C.copy()
        raise ValueError("Raw residual has no negative values, cannot achieve ratio > 1.")

    base_ratio = N / P

    if np.isclose(k, 1.0):
        target_base_ratio = 1.0
    elif k < 1.0:
        target_base_ratio = safety * k
    else:
        target_base_ratio = k / safety

    C_adj = C.copy()

    if k < 1.0:
        if base_ratio > target_base_ratio:
            alpha = target_base_ratio * P / N
            C_adj[C_adj < 0] *= alpha
    elif k > 1.0:
        if base_ratio < target_base_ratio:
            beta = N / (target_base_ratio * P)
            C_adj[C_adj > 0] *= beta
    else:
        # k == 1.0: force equal total positive/negative energy
        if not np.isclose(base_ratio, 1.0):
            if base_ratio > 1.0:
                beta = N / P
                C_adj[C_adj > 0] *= beta
            else:
                alpha = P / N
                C_adj[C_adj < 0] *= alpha

    return C_adj


def split_residual_nonnegative(C, ratio_dem_to_gen, seed=None):
    """
    Robust nonnegative split:
        generation - demand = C
        generation >= 0
        demand >= 0
        sum(demand) / sum(generation) = ratio_dem_to_gen

    This uses the shared-baseline construction, then converts it into
    an offset-profile representation.
    """
    C = np.asarray(C, dtype=float)
    k = float(ratio_dem_to_gen)

    if k <= 0:
        raise ValueError("ratio_dem_to_gen must be > 0")

    pos = np.maximum(C, 0.0)
    neg = np.maximum(-C, 0.0)

    P = pos.sum()
    N = neg.sum()

    if P == 0 and N == 0:
        z = np.zeros_like(C)
        return z, z, z, 0.5

    if np.isclose(k, 1.0):
        if not np.isclose(P, N):
            raise ValueError("ratio_dem_to_gen=1.0 requires equal total positive and negative residual.")
        A = 0.0
    else:
        A = (k * P - N) / (1.0 - k)

    if A < -1e-10:
        raise ValueError("Target ratio is infeasible for this residual series.")

    A = max(A, 0.0)

    if A > 0:
        weights = random_bumpy_series_interp(
            n=len(C),
            seed=seed,
            sharpness=1.5,
            knots=max(2, len(C) // 5),
            noise_level=0.2,
        )
        weights = np.maximum(np.asarray(weights, dtype=float), 1e-12)
        S = A * weights / weights.sum()
    else:
        S = np.zeros_like(C)

    generation = pos + S
    demand = neg + S

    # Convert to offset-profile form:
    #   generation = r * (C + offset_profile)
    #   demand     = -(1-r) * (C + offset_profile) + offset_profile
    #
    # Any 0 < r < 1 works. This choice is natural and stable.
    ratio_gen_share = 1.0 / (1.0 + k)
    offset_profile = generation / ratio_gen_share - C

    return generation, demand, offset_profile, ratio_gen_share


def create_random_time_series(
    n_phase_pairs,
    n_time_steps=None,
    ratio_dem_to_gen=1.0,
    seed=None,
):
    if n_time_steps is None:
        n_time_steps = int(n_phase_pairs*2+0.5)
    if n_phase_pairs < 1:
        raise ValueError("n_phase_pairs must be >= 1")
    if n_time_steps < 2:
        raise ValueError("n_time_steps must be >= 2")
    if ratio_dem_to_gen <= 0:
        raise ValueError("ratio_dem_to_gen must be > 0")

    rng_py = random.Random(seed)

    n_phases = 2 * n_phase_pairs
    n_time_steps = max(n_time_steps, n_phases)
    n_steps_per_phase_min = max(1, int(float(n_time_steps) / n_phases / 3))

    def _gen_random_series(n, scale=1.0):
        return [scale * rng_py.uniform(1, 10) for _ in range(int(n))]

    energy_excess = _gen_random_series(n_phase_pairs, scale=1.0)
    energy_deficit = _gen_random_series(n_phase_pairs, scale=ratio_dem_to_gen)

    energy_per_phase = np.array(
        [(e, -d) for (e, d) in zip(energy_excess, energy_deficit)],
        dtype=float
    ).flatten()

    time_steps_per_phase = np.abs(energy_per_phase).copy()
    time_steps_per_phase = (
        (time_steps_per_phase / time_steps_per_phase.sum()) * n_time_steps
    ).round().astype(int)

    time_steps_per_phase[time_steps_per_phase < n_steps_per_phase_min] = n_steps_per_phase_min
    time_step_delta = n_time_steps - int(time_steps_per_phase.sum())

    while time_step_delta != 0:
        i = rng_py.randint(0, n_phases - 1)

        if time_step_delta < 0:
            if time_steps_per_phase[i] <= n_steps_per_phase_min:
                continue
            time_steps_per_phase[i] -= 1
            time_step_delta += 1
        else:
            time_steps_per_phase[i] += 1
            time_step_delta -= 1

    assert int(time_steps_per_phase.sum()) == n_time_steps
    assert np.all(time_steps_per_phase > 0)

    def phase_energy_to_power_series(energy, n_split, local_seed):
        weights = random_bumpy_series_interp(
            n=n_split + 1,
            seed=local_seed,
            sharpness=1.5,
            knots=max(2, int(n_split / 5)),
            noise_level=0.2,
        )[:-1]

        sum_of_weights = weights.sum()
        if sum_of_weights <= 0:
            out = np.zeros(n_split, dtype=float)
            out[0] = energy
            return out

        return energy * weights / sum_of_weights

    power_residual_generation_raw = []
    rolling_seed = (seed if seed is not None else 12345) * 1000 + 17

    for phase_idx, (e, n) in enumerate(zip(energy_per_phase, time_steps_per_phase)):
        phase_seed = rolling_seed + phase_idx
        power = phase_energy_to_power_series(e, int(n), phase_seed)
        power_residual_generation_raw.extend(power)

    power_residual_generation_raw = np.asarray(power_residual_generation_raw, dtype=float)

    # Deterministically rebalance the raw residual so the requested ratio is feasible
    power_residual_generation = rebalance_residual_for_target(
        power_residual_generation_raw,
        ratio_dem_to_gen=ratio_dem_to_gen,
        safety=0.95,
    )

    power_generation, power_demand, offset_profile, ratio_gen_share = split_residual_nonnegative(
        power_residual_generation,
        ratio_dem_to_gen=ratio_dem_to_gen,
        seed=seed,
    )

    # checks
    assert np.all(power_generation >= -1e-10)
    assert np.all(power_demand >= -1e-10)
    assert np.allclose(power_generation - power_demand, power_residual_generation, atol=1e-8, rtol=1e-8)
    assert np.isclose(power_demand.sum() / power_generation.sum(), ratio_dem_to_gen, atol=1e-8, rtol=1e-8)

    return (
        power_generation,
        power_demand,
        power_residual_generation,
        power_residual_generation_raw,
        offset_profile,
        ratio_gen_share,
    )


