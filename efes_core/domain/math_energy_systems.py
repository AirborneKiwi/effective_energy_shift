import numpy as np
from typing import Union

def get_used_generation_power(power_generation: Union[np.ndarray, float, int], power_demand: Union[np.ndarray, float, int], efficiency_direct_usage: float) -> Union[np.ndarray, float, int]:
    return np.clip(power_demand/efficiency_direct_usage, a_min=0, a_max=power_generation)


def get_covered_demand_power(power_generation: Union[np.ndarray, float, int], power_demand: Union[np.ndarray, float, int], efficiency_direct_usage: float) -> Union[np.ndarray, float, int]:
    return np.clip(power_demand, a_min=0, a_max=efficiency_direct_usage*power_generation)


def calculate_energy_from_power_array(power: np.ndarray, delta_time_step: float) -> float:
    return power.sum() * delta_time_step


def calculate_energy_from_constant_power(power: Union[float, int], time_total: float) -> float:
    return power*time_total


def calculate_covered_demand_energy(power_generation: Union[np.ndarray, float, int], power_demand: Union[np.ndarray, float, int], delta_time_step: float, efficiency_direct_usage: float) -> float:
    return calculate_energy_from_power_array(power=get_covered_demand_power(power_generation=power_generation, power_demand=power_demand, efficiency_direct_usage=efficiency_direct_usage), delta_time_step=delta_time_step)


def calculate_used_generation_energy(power_generation: Union[np.ndarray, float, int], power_demand: Union[np.ndarray, float, int], delta_time_step: float, efficiency_direct_usage: float) -> float:
    return calculate_energy_from_power_array(power=get_used_generation_power(power_generation=power_generation, power_demand=power_demand, efficiency_direct_usage=efficiency_direct_usage), delta_time_step=delta_time_step)


def calculate_self_sufficiency(energy_covered_demand: float, energy_demand: float) -> float:
    return energy_covered_demand / energy_demand


def calculate_self_consumption(energy_used_generation: float, energy_generation: float) -> float:
    return energy_used_generation / energy_generation


def calculate_total_time(n_time_steps: int, delta_time_step:float) -> float:
    return n_time_steps*delta_time_step


def calculate_self_sufficiency_from_additional_energy(energy_additional: Union[float, np.ndarray], energy_demand: Union[float, np.ndarray], self_sufficiency_initial: Union[float, np.ndarray], clip: bool=True):
    self_sufficiency = self_sufficiency_initial + energy_additional/energy_demand
    if clip:
        return np.clip(self_sufficiency, 0., 1.)
    return self_sufficiency


def calculate_self_consumption_from_additional_energy(energy_additional: Union[float, np.ndarray], energy_generation: Union[float, np.ndarray], self_consumption_initial: Union[float, np.ndarray], efficiency_discharging:float, efficiency_charging:float, clip: bool=True):
    self_consumption = self_consumption_initial + energy_additional/(efficiency_charging*efficiency_discharging*energy_generation)
    if clip:
        return np.clip(self_consumption, 0., 1.)
    return self_consumption


def calculate_additional_energy_from_self_sufficiency(self_sufficiency: Union[float, np.ndarray], energy_demand: Union[float, np.ndarray], self_sufficiency_initial: Union[float, np.ndarray]):
    return (self_sufficiency-self_sufficiency_initial)*energy_demand


def calculate_additional_energy_from_self_consumption(self_consumption: Union[float, np.ndarray], energy_generation: Union[float, np.ndarray], self_consumption_initial: Union[float, np.ndarray], efficiency_discharging:float, efficiency_charging:float):
    return (self_consumption-self_consumption_initial)*energy_generation*efficiency_discharging*efficiency_charging


def calculate_self_sufficiency_from_self_consumption(self_consumption: Union[float, np.ndarray], energy_demand: Union[float, np.ndarray], energy_generation: Union[float, np.ndarray], self_consumption_initial: Union[float, np.ndarray], self_sufficiency_initial: Union[float, np.ndarray], efficiency_discharging:float, efficiency_charging:float) -> Union[float, np.ndarray]:
    return (self_consumption - self_consumption_initial)*efficiency_discharging*efficiency_charging*energy_generation/energy_demand + self_sufficiency_initial


def calculate_self_consumption_from_self_sufficiency(self_sufficiency: Union[float, np.ndarray], energy_demand: Union[float, np.ndarray], energy_generation: Union[float, np.ndarray], self_consumption_initial: Union[float, np.ndarray], self_sufficiency_initial: Union[float, np.ndarray], efficiency_discharging:float, efficiency_charging:float) -> Union[float, np.ndarray]:
    return (self_sufficiency - self_sufficiency_initial)*energy_demand/(efficiency_discharging*efficiency_charging*energy_generation) + self_consumption_initial


def calculate_capacity_from_additional_energy(energy_additional, energy_additional_array, capacity_array):
    return np.interp(x=np.clip(energy_additional, 0, energy_additional_array.max()), xp=energy_additional_array, fp=capacity_array)


def calculate_additional_energy_from_capacity(capacity, energy_additional_array, capacity_array):
    return np.interp(x=np.clip(capacity, 0, capacity_array.max()), xp=capacity_array, fp=energy_additional_array)


def calculate_gain_from_energy_and_capacity(energy_additional: Union[float, np.ndarray], capacity: Union[float, np.ndarray]) -> Union[np.ndarray, float]:
    try:
        iterator = iter(capacity)
    except TypeError:
        # not iterable
        capacity = [capacity]

    capacity_copy = np.array(capacity)
    capacity_copy[capacity_copy == 0] = -1

    gain = energy_additional / capacity_copy
    gain[capacity_copy == -1] = 0
    return gain


def calculate_effectiveness_from_gain(gain: Union[float, np.ndarray], efficiency_discharging: float):
    return gain / efficiency_discharging


def calculate_effectiveness_from_energy_and_capacity(energy_additional: Union[float, np.ndarray], capacity: Union[float, np.ndarray], efficiency_discharging: float) -> Union[np.ndarray, float]:
    return calculate_effectiveness_from_gain(calculate_gain_from_energy_and_capacity(energy_additional, capacity), efficiency_discharging)


def calculate_gain_from_effectiveness(effectiveness: Union[float, np.ndarray], efficiency_discharging: float):
    return effectiveness * efficiency_discharging


def calculate_gain_per_day(gain: Union[float, np.ndarray], time_total: float):
    return 24. * gain / time_total


def calculate_gain_per_day_from_effectiveness(effectiveness: Union[float, np.ndarray], efficiency_discharging: float, time_total: float):
    return calculate_gain_per_day(calculate_gain_from_effectiveness(effectiveness=effectiveness, efficiency_discharging=efficiency_discharging), time_total)


def calculate_effectiveness_from_gain_per_day(gain_per_day: Union[float, np.ndarray], time_total: float, efficiency_discharging: float):
    return calculate_effectiveness_from_gain(gain_per_day * time_total / 24., efficiency_discharging)

def calulate_production_to_demand_ratio(energy_generation: Union[float, np.ndarray], energy_demand: Union[float, np.ndarray]):
    """The production to demand ratio (PDR) is calculated based on the total generated energy relative to the total demanded energy irresprectively to their concurrence.
    A PDR of 1 is referred to as a net zero energy system.
    Since the concurrence of generation and demand is not considered, the PDR is not a measure of self-sufficiency!
    A PDF < 0 might (only for a system without losses!) indicate self_consumption_max = 1 for an infinite capacity of a potential storage system.
    A PDF > 0 might (only for a system without losses!) indicate self_sufficiency_max = 1 for an infinite capacity of a potential storage system.
    """
    energy_gen = np.array(energy_generation).sum() if np.isiterable(energy_generation) else energy_generation
    energy_dem = np.array(energy_demand).sum() if np.isiterable(energy_demand) else energy_demand
    return energy_gen / energy_dem


def calculate_storage_to_demand_ratio(capacity: Union[float, np.ndarray], energy_demand_per_day_mean: float):
    """The storage to demand ratio (SDR) is calculated as the ratio of the storage capacity to the mean daily energy demand."""
    return capacity / energy_demand_per_day_mean

