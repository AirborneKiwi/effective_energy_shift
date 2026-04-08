from __future__ import annotations

from collections import deque
from typing import Deque, Iterable

from efes_core.domain.enums import PacketType
from .errors import (
    InvariantViolation,
    InvalidPhaseGroupOperation,
    MergeError,
    ShiftError,
)
from .models import EnergyPacket, MefesState, PhaseGroup, PhasePair, ShiftInput

EPS = 1e-8


class PhasePairService:
    @staticmethod
    def balance(phase_pair: PhasePair) -> None:
        while phase_pair.phase_type == PacketType.UNDEFINED:
            PhasePairService.balance_first_packet(phase_pair)

    @staticmethod
    def balance_first_packet(phase_pair: PhasePair) -> None:
        if phase_pair.n_packets_excess <= 0 or phase_pair.n_packets_deficit <= 0:
            raise InvariantViolation(
                f"[{phase_pair.id}] Cannot balance first packet without both EXCESS and DEFICIT packets."
            )

        energy_packet_exs = phase_pair.pop_packet_left(PacketType.EXCESS)
        energy_packet_def = phase_pair.pop_packet_left(PacketType.DEFICIT)

        capacity_bottom = max(energy_packet_exs.capacity, energy_packet_def.capacity)
        energy_packet_exs.lift_to(capacity_bottom)
        energy_packet_def.lift_to(capacity_bottom)

        diff = energy_packet_def.energy - energy_packet_exs.energy
        energy_balanced = min(energy_packet_exs.energy, energy_packet_def.energy)

        if energy_balanced <= 0:
            raise InvariantViolation(
                f"[{phase_pair.id}] Balanced energy must be positive, got {energy_balanced}."
            )

        energy_packet_bal = energy_packet_def

        if diff > EPS:
            energy_packet_def.energy = diff
            energy_packet_def.lift_to(energy_packet_exs.capacity_max)
            phase_pair.append_packet_left(PacketType.DEFICIT, energy_packet_def)
            energy_packet_bal = energy_packet_exs
        elif diff < -EPS:
            energy_packet_exs.energy = -diff
            energy_packet_exs.lift_to(energy_packet_def.capacity_max)
            phase_pair.append_packet_left(PacketType.EXCESS, energy_packet_exs)

        energy_packet_bal.energy = energy_balanced
        phase_pair.append_packet(PacketType.BALANCED, energy_packet_bal)


class PhaseGroupService:
    @staticmethod
    def balance_group(group: PhaseGroup, state: MefesState) -> PhaseGroup:
        if group.group_type == PacketType.BALANCED:
            return group

        if group.group_type in (PacketType.DEFICIT, PacketType.EXCESS):
            raise InvalidPhaseGroupOperation(
                f"[{group.id}] Group of type {group.group_type.name} cannot be balanced."
            )

        phase_pair = state.phase_pairs[group.index_start]
        PhasePairService.balance(phase_pair)
        group.group_type = phase_pair.phase_type

        if group.group_type == PacketType.BALANCED:
            bal_lane = phase_pair.energy_packets[PacketType.BALANCED]
            top_packet = bal_lane.peek_right()
            if top_packet is None:
                raise InvariantViolation(
                    f"[{group.id}] Balanced phase pair must contain a BALANCED packet."
                )

            group.shift_inputs = [
                ShiftInput(index=None, capacity_hurdle=top_packet.capacity_max)
            ]
            return group

        group.shift_inputs = [
            ShiftInput(index=group.index_start, capacity_hurdle=0.0)
        ]
        return group

    @staticmethod
    def merge_groups(groups: Deque[PhaseGroup]) -> Deque[PhaseGroup]:
        if len(groups) < 2:
            return groups

        stack = PhaseGroupService._stack_merge(groups)
        return PhaseGroupService._boundary_merge(stack)

    @staticmethod
    def _stack_merge(groups: Iterable[PhaseGroup]) -> Deque[PhaseGroup]:
        stack: Deque[PhaseGroup] = deque()

        for group in groups:
            stack.append(group)
            PhaseGroupService._merge_end_of_stack(stack)

        return stack

    @staticmethod
    def _merge_end_of_stack(stack: Deque[PhaseGroup]) -> None:
        while len(stack) >= 2 and stack[-2].can_merge(stack[-1]):
            left = stack[-2]
            right = stack[-1]

            merged, reason = left.merge_with(right)
            if not merged:
                raise MergeError(
                    f"[{left.id}] can_merge returned True, but merge_with failed: {reason}"
                )

            stack.pop()

    @staticmethod
    def _boundary_merge(groups: Deque[PhaseGroup]) -> Deque[PhaseGroup]:
        while len(groups) > 1 and groups[-1].can_merge(groups[0]):
            left = groups[-1]
            right = groups[0]

            merged, reason = left.merge_with(right)
            if not merged:
                raise MergeError(
                    f"[{left.id}] boundary merge failed although can_merge returned True: {reason}"
                )

            groups.popleft()
            PhaseGroupService._merge_end_of_stack(groups)

        return groups

    @staticmethod
    def shift_group(group: PhaseGroup, state: MefesState) -> None:
        if group.group_type == PacketType.UNDEFINED:
            raise InvalidPhaseGroupOperation(f"[{group.id}] Cannot shift UNDEFINED group.")

        if group.group_type == PacketType.BALANCED:
            return

        if group.group_type == PacketType.DEFICIT and group.index_start == group.index_end:
            group.group_type = PacketType.UNDEFINED
            group.shift_inputs = []
            return

        index_target = PhaseGroupService._get_shift_target_index(group, state)
        try:
            phase_pair_target = state.phase_pairs[index_target]
        except IndexError as exc:
            raise ShiftError(
                f"[{group.id}] Invalid shift target index {index_target}."
            ) from exc

        capacity_hurdle = 0.0
        shift_inputs = (
            group.shift_inputs
            if group.group_type == PacketType.DEFICIT
            else reversed(group.shift_inputs)
        )

        for shift_input in shift_inputs:
            capacity_hurdle = PhaseGroupService._apply_shift_input(
                group=group,
                phase_pair_target=phase_pair_target,
                capacity_hurdle=capacity_hurdle,
                shift_input=shift_input,
                state=state,
            )

        group.group_type = (
            PacketType.UNDEFINED
            if group.group_type == PacketType.DEFICIT
            else PacketType.BALANCED
        )
        group.shift_inputs = []

    @staticmethod
    def _get_shift_target_index(group: PhaseGroup, state: MefesState) -> int:
        if group.group_type == PacketType.DEFICIT:
            return group.index_start
        return (group.index_end + 1) % state.n_phase_pairs

    @staticmethod
    def _apply_shift_input(
        group: PhaseGroup,
        phase_pair_target: PhasePair,
        capacity_hurdle: float,
        shift_input: ShiftInput,
        state: MefesState,
    ) -> float:
        index = shift_input.index
        index_target = phase_pair_target.index_phase

        if capacity_hurdle < shift_input.capacity_hurdle:
            capacity_hurdle = shift_input.capacity_hurdle

        if index is None or index == index_target:
            return capacity_hurdle

        try:
            phase_pair_source = state.phase_pairs[index]
        except IndexError as exc:
            raise ShiftError(
                f"[{group.id}] Invalid shift source index {index}."
            ) from exc

        PhaseGroupService._shift_all_from_to(
            packet_type=group.group_type,
            phase_pair_source=phase_pair_source,
            phase_pair_target=phase_pair_target,
            capacity_hurdle=capacity_hurdle,
        )
        return capacity_hurdle

    @staticmethod
    def _shift_all_from_to(
        packet_type: PacketType,
        phase_pair_source: PhasePair,
        phase_pair_target: PhasePair,
        capacity_hurdle: float,
    ) -> None:
        while phase_pair_source.n_packets[packet_type] > 0:
            PhaseGroupService._shift_one_from_to(
                packet_type=packet_type,
                phase_pair_source=phase_pair_source,
                phase_pair_target=phase_pair_target,
                capacity_hurdle=capacity_hurdle,
            )

    @staticmethod
    def _shift_one_from_to(
        packet_type: PacketType,
        phase_pair_source: PhasePair,
        phase_pair_target: PhasePair,
        capacity_hurdle: float,
    ) -> None:
        energy_packet = phase_pair_source.pop_packet_left(packet_type)

        if energy_packet.starts_below_level(capacity_hurdle):
            energy_packet.lift_to(capacity_hurdle)

        phase_pair_target.append_packet(packet_type, energy_packet)