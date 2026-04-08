from __future__ import annotations

from typing import List

import numpy as np

from efes_core.adapters.observability.observers import notify, NullObserver
from efes_core.domain.enums import PacketType
from efes_core.domain.models import AnalysisResults, EnergyPacket
from efes_core.domain.ports import EfesImplementationPort
from ..domain.ports import MefesObserverPort
from ..domain.services import PhaseGroupService
from ..domain.models import MefesState


class MefesImplementation(EfesImplementationPort):
    def __init__(self, observer: MefesObserverPort | None = None) -> None:
        self.observer = observer or NullObserver()
        self.state: MefesState = MefesState()

    def set_step(self, step:str) -> bool:
        self.state.step = step
        return notify(self.observer, self.state)

    def initialize(self, analysis_results: AnalysisResults) -> None:
        self.state = MefesState()
        self.state.energy_excess_per_phase_initial = analysis_results.energy_excess
        self.state.energy_deficit_per_phase_initial = analysis_results.energy_deficit

        analysis_results.used_method = 'mefes'
        self.state.initialize()

        self.set_step('INITIALIZED')


    def execute(self) -> List[EnergyPacket]:
        self._balance()
        self.state.n_iterations = 0

        while not self.state.done:
            self.state.n_iterations += 1
            self.set_step('NEXT ITERATION')

            self._merge()
            self._shift()
            self._balance()

        self.set_step('RUN DONE')
        return self._extract_energy_packets()

    def _extract_energy_packets(self) -> List[EnergyPacket]:
        eps = []
        for pp in self.state.phase_pairs:
            for ep in pp.energy_packets[PacketType.BALANCED]:
                eps.append(ep)
        return eps

    def _balance(self) -> None:
        self.set_step('BALANCE STARTED')
        for group in self.state.phase_groups:
            PhaseGroupService.balance_group(group, self.state)
        self.set_step('BALANCE COMPLETED')

    def _merge(self) -> None:
        self.set_step('MERGE STARTED')
        self.state.phase_groups = PhaseGroupService.merge_groups(self.state.phase_groups)
        self.set_step('MERGE COMPLETED')

    def _shift(self) -> None:
        self.set_step('SHIFT STARTED')
        for group in self.state.phase_groups:
            PhaseGroupService.shift_group(group, self.state)
        self.set_step('SHIFT COMPLETED')

