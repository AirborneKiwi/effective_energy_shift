from __future__ import annotations

from decorator_registry import register_after_many

from efes_core.domain.enums import PacketType
from ..application.use_cases import MefesImplementation
from ..domain.errors import InvariantViolation
from ..domain.models import MefesState, PhasePair
from ..domain.services import PhasePairService

ENABLED: bool = False
decorator_group = __file__
targets = [PhasePair, PhasePairService, MefesImplementation]

def _enabled() -> bool:
    return ENABLED


def check_phase_pair_invariants(pp: PhasePair) -> None:
    for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED):
        lane = pp.energy_packets[tp]
        dq = lane.dq

        if tp == PacketType.BALANCED and len(dq):
            if dq[0].capacity != 0:
                raise InvariantViolation(
                    f"[{pp.id}] First BALANCED packet must start at capacity 0."
                )

        for a, b in zip(dq, list(dq)[1:]):
            if not a.precedes(b):
                raise InvariantViolation(f"[{pp.id}] Packets not ordered canonically: {a=}, {b=}")
            if not (a.start < b.start):
                raise InvariantViolation(f"[{pp.id}] Packet starts must be strictly increasing: {a=}, {b=}")

    top_blc = pp.balanced_top()
    for tp in (PacketType.EXCESS, PacketType.DEFICIT):
        for p in pp.energy_packets[tp].dq:
            if not p.starts_at_or_above_level(top_blc):
                raise InvariantViolation(
                    f"[{pp.id}] Packet starts below balanced top: start={p.start}, balanced_top={top_blc}"
                )

    if pp.n_unbalanced_total < 0:
        raise InvariantViolation(f"[{pp.id}] n_unbalanced_total cannot be negative.")


def check_state_invariants(state: MefesState) -> None:
    energy_excess_total = sum(state.energy_excess_per_phase_initial)
    energy_deficit_total = sum(state.energy_deficit_per_phase_initial)

    energy_excess_in_packets = 0.0
    energy_deficit_in_packets = 0.0

    for phase_pair in state.phase_pairs:
        energy_exs = sum(ep.energy for ep in phase_pair.energy_packets[PacketType.EXCESS])
        energy_def = sum(ep.energy for ep in phase_pair.energy_packets[PacketType.DEFICIT])
        energy_bal = sum(ep.energy for ep in phase_pair.energy_packets[PacketType.BALANCED])

        energy_excess_in_packets += energy_exs + energy_bal
        energy_deficit_in_packets += energy_def + energy_bal

    if abs(energy_excess_in_packets - energy_excess_total) > 1e-8:
        raise InvariantViolation(
            "Energy conservation violated for EXCESS side: "
            f"packets={energy_excess_in_packets}, initial={energy_excess_total}"
        )

    if abs(energy_deficit_in_packets - energy_deficit_total) > 1e-8:
        raise InvariantViolation(
            "Energy conservation violated for DEFICIT side: "
            f"packets={energy_deficit_in_packets}, initial={energy_deficit_total}"
        )


@register_after_many(
    [
        MefesImplementation._balance,
        MefesImplementation._shift,
    ],
    group=decorator_group,
    enabled=_enabled,
)
def _check_state_after_step(res, self: MefesImplementation, *a, **k):
    check_state_invariants(self.state)


@register_after_many(
    [
        PhasePair.enforce_above_balanced,
        PhasePair.append_packet,
        PhasePair.append_packet_left,
        PhasePair.pop_packet,
        PhasePair.pop_packet_left,
        PhasePairService.balance,
        PhasePairService.balance_first_packet,
    ],
    group=decorator_group,
    enabled=_enabled,
)
def _check_phase_pair_after_any(res, self, *a, **k):
    # self is either a PhasePair instance or PhasePairService class/static target context
    if isinstance(self, PhasePair):
        check_phase_pair_invariants(self)
        return