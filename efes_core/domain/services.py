from typing import List

import numpy as np
from efes_core.domain.runlength_utils import rlencode
from efes_core.domain import math_energy_systems as mes

from efes_core.domain.errors import InvalidQueryError, InvalidInputError, NoDeficitError, NoExcessError
from efes_core.domain.models import EnergyPacket, ParameterStudyResults, QueryResults, QueryInput, AnalysisResults, \
    EfesInput

def runlength_encode(array_to_encode: np.ndarray, loop_around: bool = True):
    """
    A function that performs run length encoding and simplifies the encoded results by combining matching start and ends.
    :param array_to_encode: The array that shall be encoded
    :param loop_around: (optional) If set to False, no simplification will be performed. Defaults to True.
    :return: The run length encoding (starts, lengths and values) describing the original array.
    """
    n_time_steps = array_to_encode.size
    starts, lengths, values = rlencode(array_to_encode)
    if len(values) == 1:
        starts = np.array([0, n_time_steps - 1])
        lengths = np.array([n_time_steps, 0])
        if values[0]:
            """All values are True"""
            return starts, lengths, np.array([values[0], 0])
        """All values are False"""
        return starts, lengths, np.array([False, True])

    if not loop_around:
        return starts, lengths, values

    """
    Set a correct start for looping
    If we have all 1, the solution is trivial -> we return full flooding
    If we have all 0, the solution is trivial -> we return a linear increase of flooding
    If the first part is a 0, put it at the back
    If the first and last part is a 1, put the back at front
    """
    if values[0] == 0 and values[-1] == 0:
        """If the first and last part is zero, append the front to the end"""
        # starts -= starts[1]  # keep the indices for later decoding
        lengths[-1] = lengths[-1] + lengths[0]
        starts = starts[1:]
        lengths = lengths[1:]
        values = values[1:]
    elif values[0] == 0:
        """If the first part is a 0, put it at the back"""
        starts = np.roll(starts, 1)
        lengths = np.roll(lengths, 1)
        values = np.roll(values, 1)
    elif values[0] == 1 and values[-1] == 1:
        """If the first and last part is one, append the end to the front"""
        # starts -= starts[1]  # keep the indices for later decoding
        lengths[0] = lengths[0] + lengths[-1]
        starts[0] = starts[-1]
        starts = starts[:-1]
        lengths = lengths[:-1]
        values = values[:-1]

    return starts, lengths, values


def calculate_energy_per_phase(
    power_residual_generation: np.ndarray,
    power_max_discharging: float,
    power_max_charging: float,
    efficiency_discharging: float,
    efficiency_charging: float,
    delta_time_step: float,
):
    starts_zero, lengths_zero, values_zero = runlength_encode(power_residual_generation >= 0)
    power_residual_generation_clipped = np.clip(
        power_residual_generation,
        -power_max_discharging,
        power_max_charging,
    )

    n_phases = int(starts_zero.shape[0] / 2)
    energy_excess = np.zeros(shape=(n_phases,))
    energy_deficit = np.zeros(shape=(n_phases,))

    for n in range(0, starts_zero.shape[0], 2):
        generation = power_residual_generation_clipped[
            np.arange(starts_zero[n], starts_zero[n] + lengths_zero[n]) % power_residual_generation_clipped.size
        ].sum() * delta_time_step
        demand = power_residual_generation_clipped[
            np.arange(starts_zero[n + 1], starts_zero[n + 1] + lengths_zero[n + 1]) % power_residual_generation_clipped.size
        ].sum() * delta_time_step
        energy_excess[int(n / 2)] = generation
        energy_deficit[int(n / 2)] = -demand

    return dict(
        starts_phases=starts_zero,
        lengths_phases=lengths_zero,
        values_phases=values_zero,
        power_residual_generation_clipped=power_residual_generation_clipped,
        N_phases=n_phases,
        energy_excess_wo_efficiency=energy_excess.copy(),
        energy_deficit_wo_efficiency=energy_deficit.copy(),
        energy_excess=efficiency_charging * energy_excess,
        energy_deficit=(1.0 / efficiency_discharging) * energy_deficit,
    )


def calculate_initial_self_sufficiency_and_self_consumption(
    power_generation,
    power_demand,
    delta_time_step: float,
    efficiency_direct_usage: float,
):
    time_total = None
    if isinstance(power_demand, (float, int)):
        time_total = delta_time_step * power_generation.size
        energy_demand = mes.calculate_energy_from_constant_power(power=power_demand, time_total=time_total)
    else:
        time_total = delta_time_step * power_demand.size
        energy_demand = mes.calculate_energy_from_power_array(power_demand, delta_time_step)

    if isinstance(power_generation, (float, int)):
        time_total = delta_time_step * power_demand.size
        energy_generation = mes.calculate_energy_from_constant_power(power=power_generation, time_total=time_total)
    else:
        time_total = delta_time_step * power_generation.size
        energy_generation = mes.calculate_energy_from_power_array(power_generation, delta_time_step)

    energy_used_generation = mes.calculate_used_generation_energy(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=delta_time_step,
        efficiency_direct_usage=efficiency_direct_usage,
    )
    energy_covered_demand = mes.calculate_covered_demand_energy(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=delta_time_step,
        efficiency_direct_usage=efficiency_direct_usage,
    )
    self_sufficiency = mes.calculate_self_sufficiency(
        energy_covered_demand=energy_covered_demand,
        energy_demand=energy_demand,
    )
    self_consumption = mes.calculate_self_consumption(
        energy_used_generation=energy_used_generation,
        energy_generation=energy_generation,
    )

    return dict(
        self_sufficiency_initial=self_sufficiency,
        self_consumption_initial=self_consumption,
        energy_used_generation=energy_used_generation,
        energy_covered_demand=energy_covered_demand,
        energy_demand=energy_demand,
        energy_generation=energy_generation,
        time_total=time_total,
    )

def analyse_power_data(
    power_generation,
    power_demand,
    delta_time_step,
    power_max_discharging=np.inf,
    power_max_charging=np.inf,
    efficiency_direct_usage=1.0,
    efficiency_discharging=1.0,
    efficiency_charging=1.0,
):
    power_covered_demand = mes.get_covered_demand_power(
        power_generation=power_generation,
        power_demand=power_demand,
        efficiency_direct_usage=efficiency_direct_usage,
    )
    power_used_generation = mes.get_used_generation_power(
        power_generation=power_generation,
        power_demand=power_demand,
        efficiency_direct_usage=efficiency_direct_usage,
    )
    power_residual_generation = (
        power_generation - power_demand - (power_used_generation - power_covered_demand)
    )

    data_input = EfesInput(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=delta_time_step,
        power_used_generation=power_used_generation,
        power_covered_demand=power_covered_demand,
        power_residual_generation=power_residual_generation,
        power_max_discharging=power_max_discharging,
        power_max_charging=power_max_charging,
        efficiency_direct_usage=efficiency_direct_usage,
        efficiency_discharging=efficiency_discharging,
        efficiency_charging=efficiency_charging,
    )

    validate_analysis_input(data_input)

    analysis_results = AnalysisResults(
        data_input=data_input,
        **calculate_initial_self_sufficiency_and_self_consumption(
            power_generation=data_input.power_generation,
            power_demand=data_input.power_demand,
            delta_time_step=data_input.delta_time_step,
            efficiency_direct_usage=data_input.efficiency_direct_usage,
        ),
        **calculate_energy_per_phase(
            power_residual_generation=data_input.power_residual_generation,
            power_max_discharging=data_input.power_max_discharging,
            power_max_charging=data_input.power_max_charging,
            efficiency_discharging=data_input.efficiency_discharging,
            efficiency_charging=data_input.efficiency_charging,
            delta_time_step=data_input.delta_time_step,
        )
    )

    return analysis_results


def validate_analysis_input(data_input: EfesInput) -> None:
    residual = data_input.power_residual_generation
    try:
        _ = residual[0]
    except TypeError as exc:
        raise InvalidInputError("Either power_generation or power_demand must be iterable.") from exc

    if np.all(residual > 0):
        raise NoDeficitError(
            "There is no deficit in the given power data. Therefore, the self-sufficiency is already 1 and no storage system will increase it."
        )
    if np.all(residual < 0):
        raise NoExcessError(
            "There is no excess in the given power data. Therefore, the self-consumption is already 1 and no storage system will increase it."
        )

    if data_input.delta_time_step == 0:
        raise InvalidInputError("delta_time_step must be non-zero.")
    if data_input.power_max_discharging <= 0:
        raise InvalidInputError("power_max_discharging must be greater than zero.")
    if data_input.power_max_charging <= 0:
        raise InvalidInputError("power_max_charging must be greater than zero.")
    if data_input.efficiency_direct_usage <= 0 or data_input.efficiency_discharging <= 0 or data_input.efficiency_charging <= 0:
        raise InvalidInputError("All efficiencies must be greater than zero.")


def collect_and_count(energy_packets: List[EnergyPacket]):
    eps = 8
    multiplier = 10 ** eps
    capacity_list = np.array([ep.capacity for ep in energy_packets])
    capacity_max_list = np.array([ep.capacity_max for ep in energy_packets])

    capacity_raw_ints = np.round(
        np.array([(ep.capacity, ep.capacity_max) for ep in energy_packets]).flatten() * multiplier).astype(np.int64)
    capacity_sorted_ints = np.sort(capacity_raw_ints)

    mask = np.ones(len(capacity_sorted_ints), dtype=np.bool_)
    mask[1:] = np.diff(capacity_sorted_ints) > 0
    capacity_ints = capacity_sorted_ints[mask]

    capacity = capacity_ints / multiplier

    effectiveness_local = np.zeros(len(capacity))
    starts_ints = np.round(capacity_list * multiplier).astype(np.int64)
    ends_ints = np.round(capacity_max_list * multiplier).astype(np.int64)
    for start, end in zip(starts_ints, ends_ints):
        effectiveness_local[(start <= capacity_ints) & (capacity_ints < end)] += 1

    keep_mask = np.diff(effectiveness_local, prepend=-1) != 0

    capacity = capacity[keep_mask]
    effectiveness_local = effectiveness_local[keep_mask]

    return capacity, effectiveness_local

def calculate_additional_energy(capacity, effectiveness_local, efficiency_discharging):
    delta_capacity = np.diff(capacity)
    delta_energy_additional = effectiveness_local[:-1] * delta_capacity
    energy_additional = efficiency_discharging * np.array([0, *delta_energy_additional.cumsum()])
    return energy_additional


def run_dimensioning_query_for_target_self_sufficiency(analysis_results, self_sufficiency_target) -> QueryResults:
    return run_query(
        analysis_results=analysis_results,
        query_results=QueryResults(query_input=QueryInput(self_sufficiency_target=self_sufficiency_target)),
    )

def run_dimensioning_query_for_target_self_consumption(analysis_results, self_consumption_target) -> QueryResults:
    return run_query(
        analysis_results=analysis_results,
        query_results=QueryResults(query_input=QueryInput(self_consumption_target=self_consumption_target)),
    )

def run_dimensioning_query_for_target_additional_energy(analysis_results, energy_additional_target) -> QueryResults:
    return run_query(
        analysis_results=analysis_results,
        query_results=QueryResults(query_input=QueryInput(energy_additional_target=energy_additional_target)),
    )

def run_dimensioning_query_for_target_capacity(analysis_results, capacity_target) -> QueryResults:
    return run_query(
        analysis_results=analysis_results,
        query_results=QueryResults(query_input=QueryInput(capacity_target=capacity_target)),
    )

def run_query(analysis_results: AnalysisResults, query_results: QueryResults) -> QueryResults:
    if query_results.query_input is None or query_results.query_input.count_targets() != 1:
        raise InvalidQueryError("Exactly one query target must be provided.")

    self_sufficiency_target = query_results.query_input.self_sufficiency_target
    self_consumption_target = query_results.query_input.self_consumption_target
    energy_additional_target = query_results.query_input.energy_additional_target
    capacity_target = query_results.query_input.capacity_target

    if self_sufficiency_target is not None:
        query_results.self_sufficiency = np.clip(
            a=self_sufficiency_target,
            a_min=analysis_results.self_sufficiency_initial,
            a_max=analysis_results.self_sufficiency_max,
        )
        query_results.self_consumption = mes.calculate_self_consumption_from_self_sufficiency(
            self_sufficiency=query_results.self_sufficiency,
            energy_demand=analysis_results.energy_demand,
            energy_generation=analysis_results.energy_generation,
            self_consumption_initial=analysis_results.self_consumption_initial,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
            efficiency_discharging=analysis_results.data_input.efficiency_discharging,
            efficiency_charging=analysis_results.data_input.efficiency_charging,
        )
        query_results.energy_additional = mes.calculate_additional_energy_from_self_sufficiency(
            self_sufficiency=query_results.self_sufficiency,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
            energy_demand=analysis_results.energy_demand,
        )
        query_results.capacity = mes.calculate_capacity_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_additional_array=analysis_results.energy_additional,
            capacity_array=analysis_results.capacity,
        )
    elif self_consumption_target is not None:
        query_results.self_consumption = np.clip(
            a=self_consumption_target,
            a_min=analysis_results.self_consumption_initial,
            a_max=analysis_results.self_consumption_max,
        )
        query_results.self_sufficiency = mes.calculate_self_sufficiency_from_self_consumption(
            self_consumption=query_results.self_consumption,
            energy_demand=analysis_results.energy_demand,
            energy_generation=analysis_results.energy_generation,
            self_consumption_initial=analysis_results.self_consumption_initial,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
            efficiency_discharging=analysis_results.data_input.efficiency_discharging,
            efficiency_charging=analysis_results.data_input.efficiency_charging,
        )
        query_results.energy_additional = mes.calculate_additional_energy_from_self_sufficiency(
            self_sufficiency=query_results.self_sufficiency,
            energy_demand=analysis_results.energy_demand,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
        )
        query_results.capacity = mes.calculate_capacity_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_additional_array=analysis_results.energy_additional,
            capacity_array=analysis_results.capacity,
        )
    elif energy_additional_target is not None:
        query_results.energy_additional = np.clip(
            a=energy_additional_target,
            a_min=0.0,
            a_max=analysis_results.energy_additional_max,
        )
        query_results.self_sufficiency = mes.calculate_self_sufficiency_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_demand=analysis_results.energy_demand,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
        )
        query_results.self_consumption = mes.calculate_self_consumption_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_generation=analysis_results.energy_generation,
            self_consumption_initial=analysis_results.self_consumption_initial,
            efficiency_charging=analysis_results.data_input.efficiency_charging,
            efficiency_discharging=analysis_results.data_input.efficiency_discharging,
        )
        query_results.capacity = mes.calculate_capacity_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_additional_array=analysis_results.energy_additional,
            capacity_array=analysis_results.capacity,
        )
    elif capacity_target is not None:
        query_results.capacity = np.clip(a=capacity_target, a_min=0.0, a_max=None)
        query_results.energy_additional = mes.calculate_additional_energy_from_capacity(
            capacity=query_results.capacity,
            energy_additional_array=analysis_results.energy_additional,
            capacity_array=analysis_results.capacity,
        )
        query_results.self_sufficiency = mes.calculate_self_sufficiency_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_demand=analysis_results.energy_demand,
            self_sufficiency_initial=analysis_results.self_sufficiency_initial,
        )
        query_results.self_consumption = mes.calculate_self_consumption_from_additional_energy(
            energy_additional=query_results.energy_additional,
            energy_generation=analysis_results.energy_generation,
            self_consumption_initial=analysis_results.self_consumption_initial,
            efficiency_discharging=analysis_results.data_input.efficiency_discharging,
            efficiency_charging=analysis_results.data_input.efficiency_charging,
        )

    indices = np.searchsorted(analysis_results.capacity, query_results.capacity, side="right" ) - 1
    query_results.effectiveness_local = analysis_results.effectiveness_local[indices]
    query_results.gain = mes.calculate_gain_from_energy_and_capacity(
        energy_additional=query_results.energy_additional,
        capacity=query_results.capacity,
    )
    query_results.effectiveness = mes.calculate_effectiveness_from_gain(
        gain=query_results.gain,
        efficiency_discharging=analysis_results.data_input.efficiency_discharging,
    )
    query_results.gain_per_day = mes.calculate_gain_per_day(
        gain=query_results.gain,
        time_total=analysis_results.time_total,
    )
    return query_results
