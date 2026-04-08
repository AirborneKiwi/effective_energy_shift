from typing import List

import numpy as np

from efes_core.domain.ports import EfesImplementationPort, ObserverPort
from efes_core.domain import math_energy_systems as mes

from efes_core.domain.models import AlgorithmState, AnalysisResults, Results, EfesInput, EnergyPacket
from efes_core.domain.services import (
    run_dimensioning_query_for_target_self_sufficiency,
    run_dimensioning_query_for_target_self_consumption,
    run_dimensioning_query_for_target_additional_energy,
    run_dimensioning_query_for_target_capacity, collect_and_count, calculate_additional_energy, analyse_power_data,
)
from efes_core.adapters.observability.observers import notify
from efes_core.scripts.chronological_ref_alg import run_chronological_algorithm


class EfesAlgorithmRunner:
    def __init__(self, impl: EfesImplementationPort, observer = None):
        self.impl = impl
        self.observer = observer
        self.state: AlgorithmState = AlgorithmState()
        self.state.step = "NOT_INITIALIZED"
        self.results: Results = Results()

    def set_step(self, step) -> bool:
        """Set the state of the algorithm and notify observers. Return a bool indicating whether to stop or not."""
        self.state.step = step
        return notify(self.observer, self.state)

    def initialize(self,
                   power_generation,
                   power_demand,
                   delta_time_step,
                   power_max_discharging=np.inf,
                   power_max_charging=np.inf,
                   efficiency_direct_usage=1.0,
                   efficiency_discharging=1.0,
                   efficiency_charging=1.0,
                   ) -> AnalysisResults:
        """Analyse the provided power data and initialize data structures for the execution of the algorithms implementation"""
        self.analysis_results = analyse_power_data(
            power_generation=power_generation,
            power_demand=power_demand,
            delta_time_step=delta_time_step,
            power_max_discharging=power_max_discharging,
            power_max_charging=power_max_charging,
            efficiency_direct_usage=efficiency_direct_usage,
            efficiency_discharging=efficiency_discharging,
            efficiency_charging=efficiency_charging,
        )
        self.impl.initialize(self.analysis_results)
        self.set_step("INITIALIZED")
        return self.analysis_results

    @property
    def analysis_results(self) -> AnalysisResults | None:
        if self.results is None:
            return None
        return self.results.analysis_results

    @analysis_results.setter
    def analysis_results(self, value: AnalysisResults):
        self.results.analysis_results = value

    @property
    def data_input(self) -> EfesInput | None:
        if self.analysis_results is None:
            return None
        return self.results.analysis_results.data_input


    def execute(self) -> AnalysisResults:
        """Execute the actual implementation of the algorithm"""
        energy_packets = self.impl.execute()

        self.set_step('COLLECT & COUNT')

        capacity, effectiveness_local = collect_and_count(energy_packets)

        energy_additional = calculate_additional_energy(
            capacity=capacity,
            effectiveness_local=effectiveness_local,
            efficiency_discharging=self.data_input.efficiency_discharging,
        )

        self.analysis_results.capacity = capacity
        self.analysis_results.energy_additional = energy_additional
        self.analysis_results.effectiveness_local = effectiveness_local

        self.analysis_results.capacity_max = self.analysis_results.capacity[-1]
        self.analysis_results.energy_additional_max = self.analysis_results.energy_additional[-1]

        self.analysis_results.self_sufficiency = mes.calculate_self_sufficiency_from_additional_energy(
            energy_additional=self.analysis_results.energy_additional,
            energy_demand=self.analysis_results.energy_demand,
            self_sufficiency_initial=self.analysis_results.self_sufficiency_initial,
        )
        self.analysis_results.self_sufficiency_max = (
                self.analysis_results.self_sufficiency_initial + self.analysis_results.energy_additional_max / self.analysis_results.energy_demand
        )

        self.analysis_results.self_consumption = mes.calculate_self_consumption_from_additional_energy(
            energy_additional=self.analysis_results.energy_additional,
            energy_generation=self.analysis_results.energy_generation,
            self_consumption_initial=self.analysis_results.self_consumption_initial,
            efficiency_discharging=self.data_input.efficiency_discharging,
            efficiency_charging=self.data_input.efficiency_charging,
        )

        self.analysis_results.self_consumption_max = self.analysis_results.self_consumption_initial + self.analysis_results.energy_additional_max / (self.data_input.efficiency_charging * self.data_input.efficiency_discharging * self.analysis_results.energy_generation)

        self.set_step('DONE')
        return self.analysis_results


    def query(self,
              self_sufficiency_target=None,
              self_consumption_target=None,
              energy_additional_target=None,
              capacity_target=None,
              ) -> Results:
        """Query the results for specific targets"""
        query_results = []
        if self_sufficiency_target is not None:
            query_results.append(
                run_dimensioning_query_for_target_self_sufficiency(self.results.analysis_results, self_sufficiency_target))
        if self_consumption_target is not None:
            query_results.append(
                run_dimensioning_query_for_target_self_consumption(self.results.analysis_results, self_consumption_target))
        if energy_additional_target is not None:
            query_results.append(
                run_dimensioning_query_for_target_additional_energy(self.results.analysis_results, energy_additional_target))
        if capacity_target is not None:
            query_results.append(run_dimensioning_query_for_target_capacity(self.results.analysis_results, capacity_target))

        self.results.query_results = query_results or None
        return self.results


class ChronoRefImpl(EfesImplementationPort):
    def __init__(self, capacity_min:float, capacity_max:float, n_samples:int=100, observer: ObserverPort = None):
        self.observer = observer
        self.capacity_min:float = capacity_min
        self.capacity_max:float = capacity_max
        self.n_samples:int = n_samples
        self.state = AlgorithmState()

    def set_step(self, step:str) -> bool:
        self.state.step = step
        return notify(self.observer, self.state)

    def initialize(self, analysis_results: AnalysisResults) -> None:
        self.capacity_target = np.linspace(self.capacity_min, self.capacity_max, num=self.n_samples)
        self.energy_additional_over_time = [None]*len(self.capacity_target)
        self.analysis_results = analysis_results
        self.analysis_results.used_method = 'chrono. ref.'
        self.set_step('INITIALIZE')

    def execute(self) -> List[EnergyPacket]:
        for i, capacity in enumerate(self.capacity_target):
            self.energy_additional_over_time[i] = run_chronological_algorithm(
                power_generation=self.analysis_results.data_input.power_generation,
                power_demand=self.analysis_results.data_input.power_demand,
                delta_time_step=self.analysis_results.data_input.delta_time_step,
                capacity=capacity,
                charge_initial=0,
                power_max_charging=self.analysis_results.data_input.power_max_charging,
                power_max_discharging=self.analysis_results.data_input.power_max_discharging,
                efficiency_charging=self.analysis_results.data_input.efficiency_charging,
                efficiency_discharging=self.analysis_results.data_input.efficiency_discharging,
                efficiency_direct_usage=self.analysis_results.data_input.efficiency_direct_usage,
            )

        self.analysis_results.energy_additional = np.array(self.energy_additional_over_time).sum(axis=1)
        energy_deltas = np.diff(self.analysis_results.energy_additional)/self.analysis_results.data_input.efficiency_discharging
        capacity_deltas = np.diff(self.capacity_target)
        effectiveness_local = energy_deltas / capacity_deltas
        energy_packets = []
        c = 0
        for i in range(len(capacity_deltas)):
            m = int(round(effectiveness_local[i]))
            e = capacity_deltas[i]
            for _ in range(round(m)):
                energy_packets.append(EnergyPacket(c, e))
            c += e

        return energy_packets