from decorator_registry import register_after_many
from typing import Callable
from functools import wraps

ENABLED: bool = False
decorator_group = __file__
def _enabled() -> bool:
    return ENABLED

from mefes_dataclasses import Context, PhasePair, PhaseGroup, PacketType, EnergyPacket, EnergyPacketLane


def check_phase_pair_invariants(pp: PhasePair):
    for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED):
        lane = pp.energy_packets[tp]
        dq = lane.dq

        if tp == PacketType.BALANCED and len(dq):
            assert dq[0].capacity == 0

        for a, b in zip(dq, list(dq)[1:]):
            # canonical ordering + no overlaps (contact OK)
            assert a.precedes(b), f"{a = }, {b = }"
            assert a.start < b.start

    top_blc = pp._balanced_top()
    for tp in (PacketType.EXCESS, PacketType.DEFICIT):
        for p in pp.energy_packets[tp].dq:
            assert p.starts_at_or_above_level(top_blc), f"{p.start} and {top_blc}"

    assert pp.N_unbalanced_total >= 0


def check_context_invariants(ctx: Context):
    energy_excess_total = sum(ctx.energy_excess_per_phase_initial)
    energy_deficit_total = sum(ctx.energy_deficit_per_phase_initial)

    energy_excess_in_packets = 0
    energy_deficit_in_packets = 0
    for phase_pair in ctx.phase_pairs:
        energy_exs = sum([ep.energy for ep in phase_pair.energy_packets[PacketType.EXCESS]])
        energy_def = sum([ep.energy for ep in phase_pair.energy_packets[PacketType.DEFICIT]])
        energy_bal = sum([ep.energy for ep in phase_pair.energy_packets[PacketType.BALANCED]])

        energy_excess_in_packets += energy_exs + energy_bal
        energy_deficit_in_packets += energy_def + energy_bal

    print(f'Energy difference EXCESS = {energy_excess_in_packets-energy_excess_total}')
    print(f'Energy difference DEFICIT = {energy_deficit_in_packets - energy_deficit_total}')


@register_after_many([
    Context.balance,
    Context.shift,
], group=decorator_group, enabled=_enabled)
def _check_ctx_after_shift(self: Context, _res, *a, **k):
    check_context_invariants(self)


@register_after_many([
    PhasePair.enforce_above_balanced,
    PhasePair.append_packet,
    PhasePair.append_packet_left,
    PhasePair.pop_packet,
    PhasePair.pop_packet_left,
    PhasePair.balance,
], group=decorator_group, enabled=_enabled)
def _check_pp_after_any(self: PhasePair, _res, *a, **k):
    check_phase_pair_invariants(self)