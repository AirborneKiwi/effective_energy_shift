from __future__ import annotations

from typing import List

import numpy as np

from efes_core.adapters.observability.observers import notify
from ..domain.models import EfesState, Phase
from ..domain.ports import EfesObserverPort
from ..domain.services import (
    extract_energy_packets,
    balance_phase,
    remove_excess,
    add_excess_to_phase,
    calculate_virtual_excess,
)
from efes_core.domain.ports import AnalysisResults, EnergyPacket


class EfesImplementation:
    def __init__(self, observer: EfesObserverPort | None = None) -> None:
        self.observer = observer
        self.state: EfesState = EfesState()

    def set_step(self, step:str) -> bool:
        self.state.step = step
        return notify(self.observer, self.state)

    def initialize(self, analysis_results: AnalysisResults) -> None:
        energy_excess = analysis_results.energy_excess
        energy_deficit = analysis_results.energy_deficit
        start_time_phases = analysis_results.data_input.delta_time_step * analysis_results.starts_phases
        analysis_results.used_method = 'efes'

        self.state = EfesState()
        self.state.phases = np.array([
            Phase(excess, deficit, id=start_time_phase)
            for excess, deficit, start_time_phase in zip(energy_excess, energy_deficit, start_time_phases)
        ])
        self.state.mask = None
        self.set_step('INITIALIZE')

    def execute(self) -> List[EnergyPacket]:
        """Perform the effective energy shift (EfES) algorithm in on the input."""

        while True:
            if self._balance():
                break

            if np.any(~np.any(self.state.mask, axis=1)):
                break

            if self._shift_and_settle():
                break

        return extract_energy_packets(self.state)

    def _balance(self) -> bool:
        if self.state.mask is None:
            self.state.mask = np.ones((2, len(self.state.phases)), dtype=bool)

        potential_balance = self.state.mask[0] & self.state.mask[1]
        self.state.mask[:, potential_balance] = np.array(
            list(map(balance_phase, self.state.phases[potential_balance]))).transpose()

        return self.set_step("BALANCE")

    def _shift_and_settle(self):
        add_virtual_excess_mask = np.roll(self.state.mask[0], shift=1)
        next_indices = (np.arange(len(self.state.mask[0]))[self.state.mask[0]] + 1) % len(self.state.mask[0])
        current_phases = self.state.phases[self.state.mask[0]]
        next_phases = self.state.phases[next_indices]
        virtual_excess = list(map(lambda args: calculate_virtual_excess(*args), zip(current_phases, next_phases)))
        list(map(lambda args: add_excess_to_phase(args[0], *args[1]),
                 zip(self.state.phases[next_indices], virtual_excess)))

        if self.set_step("SHIFT"):
            return True

        list(map(lambda phase: remove_excess(phase, -2),
                 self.state.phases[self.state.mask[0] & add_virtual_excess_mask]))
        list(map(lambda phase: remove_excess(phase, -1),
                 self.state.phases[self.state.mask[0] & ~add_virtual_excess_mask]))

        self.state.mask[0] = add_virtual_excess_mask

        return self.set_step("SETTLE")
