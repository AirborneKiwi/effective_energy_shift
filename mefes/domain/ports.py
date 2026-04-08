from __future__ import annotations

from typing import Protocol, Sequence

from .models import MefesState, PhaseGroup, PhasePair, ShiftInput

class MefesObserverPort(Protocol):
    """
    Outbound port for logging, tracing, TeX export, event recording, etc.
    The domain/application can depend on this without knowing the concrete sink.
    """

    def on_run_started(self, state: MefesState) -> None: ...
    def on_iteration_started(self, iteration: int, state: MefesState) -> None: ...
    def on_balance_started(self, state: MefesState) -> None: ...
    def on_balance_completed(self, state: MefesState) -> None: ...
    def on_merge_started(self, state: MefesState) -> None: ...
    def on_merge_completed(self, state: MefesState) -> None: ...
    def on_shift_started(self, state: MefesState) -> None: ...
    def on_shift_completed(self, state: MefesState) -> None: ...
    def on_run_completed(self, state: MefesState) -> None: ...


class PhasePairBalancerPort(Protocol):
    """
    Inbound domain port for balancing a single phase pair.
    A use case can depend on this if you want balancing strategy to be swappable.
    """

    def balance(self, phase_pair: PhasePair) -> None: ...


class PhaseGroupBalancerPort(Protocol):
    """
    Inbound domain port for resolving an UNDEFINED phase group into
    EXCESS / DEFICIT / BALANCED and computing its shift inputs.
    """

    def balance_group(self, group: PhaseGroup, state: MefesState) -> None: ...


class PhaseGroupShifterPort(Protocol):
    """
    Inbound domain port for executing the shift semantics of one phase group.
    """

    def shift_group(self, group: PhaseGroup, state: MefesState) -> None: ...


class PhaseGroupMergerPort(Protocol):
    """
    Inbound domain port for reducing a sequence of groups using merge rules.
    """

    def merge_groups(self, groups: Sequence[PhaseGroup], state: MefesState) -> Sequence[PhaseGroup]: ...


class ResultFormatterPort(Protocol):
    """
    Outbound port for presentation adapters such as console tables, TeX, JSON, etc.
    """

    def format_state(self, state: MefesState) -> str: ...


class ScenarioProviderPort(Protocol):
    """
    Optional inbound port for benchmark/example/random initializers.
    Keeps scenario construction outside the domain.
    """

    def build_state(self) -> MefesState: ...