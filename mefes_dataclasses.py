from enum import IntEnum
from dataclasses import dataclass, field, InitVar
from typing import Deque, List, Dict, Tuple, Optional, Iterator
from collections import deque

EPS = 1e-8

class PacketType(IntEnum):
    EXCESS = 0
    DEFICIT = 1
    BALANCED = 2
    UNDEFINED = 3


@dataclass
class EnergyPacket:
    capacity: float
    energy: float

    def __post_init__(self):
        if self.capacity < 0:
            raise ValueError("capacity must be non-negative")

        if self.energy <= 0:
            raise ValueError("energy must be positive")

    @property
    def capacity_max(self) -> float:
        return self.capacity + self.energy

    @property
    def start(self) -> float:
        return self.capacity

    @property
    def end(self) -> float:
        return self.capacity_max

    def precedes(self, other: "EnergyPacket") -> bool:
        """True if self is entirely before other (allowing contact within EPS)."""
        return self.end <= other.start + EPS

    def starts_below_level(self, level: float) -> bool:
        """True if self.start is below `level` by more than EPS."""
        return self.start + EPS < level

    def starts_at_or_above_level(self, level: float) -> bool:
        return not self.starts_below_level(level)

    def starts_below(self, other: "EnergyPacket") -> bool:
        return self.start + EPS < other.start

    def starts_above(self, other: "EnergyPacket") -> bool:
        return self.start > other.end + EPS

    def starts_within(self, other: "EnergyPacket") -> bool:
        return not (self.starts_below(other) or self.starts_above(other))

    def ends_below(self, other: "EnergyPacket") -> bool:
        return self.end + EPS < other.start

    def ends_above(self, other: "EnergyPacket") -> bool:
        return self.end > other.end + EPS

    def ends_within(self, other: "EnergyPacket") -> bool:
        return not (self.ends_below(other) or self.ends_above(other))

    def _delta(self, other: "EnergyPacket") -> float:
        left = max(self.capacity, other.capacity)
        right = min(self.capacity_max, other.capacity_max)
        return right - left

    def overlaps_with(self, other: "EnergyPacket") -> bool:
        """Overlap INCLUDING contact (within EPS)."""
        return self._delta(other) >= -EPS

    def contact_with(self, other: "EnergyPacket") -> bool:
        """True if they touch (intersection ~ 0), within EPS tolerance."""
        return abs(self._delta(other)) <= EPS

    def overlap_or_contact(self, other: "EnergyPacket") -> bool:
        return self.overlaps_with(other)

    def overlaps_strictly_with(self, other: "EnergyPacket") -> bool:
        """Strict positive-length overlap beyond EPS (touch/contact is NOT strict)."""
        return self._delta(other) > EPS


    def lift_to(self, level: float) -> 'EnergyPacket':
        """Allows increasing the capacity to a level, but never allows lowering."""
        if self.starts_below_level(level):
            self.capacity = level

        return self


class PacketLaneError(ValueError): ...
class PacketOverlapError(PacketLaneError): ...
class PacketOrderError(PacketLaneError): ...


@dataclass
class EnergyPacketLane:
    lane_type: PacketType
    dq: Deque[EnergyPacket] = field(default_factory=deque)

    @property
    def ID(self) -> str:
        return f'{self.lane_type.name} Lane'

    def __len__(self) -> int:
        return len(self.dq)

    def __iter__(self) -> Iterator[EnergyPacket]:
        return iter(self.dq)

    def peek_left(self) -> Optional[EnergyPacket]:
        return self.dq[0] if self.dq else None

    def peek_right(self) -> Optional[EnergyPacket]:
        return self.dq[-1] if self.dq else None

    def pop_left(self) -> EnergyPacket:
        return self.dq.popleft()

    def pop_right(self) -> EnergyPacket:
        return self.dq.pop()

    def append_packet(self, energy_packet: EnergyPacket) -> 'EnergyPacketLane':
        """
        Tail-append:
          - merges touching (within EPS)
          - raises on strict overlap
          - raises if start order goes backwards
        """
        if not self.dq:
            self.dq.append(energy_packet)
            return self

        last = self.dq[-1]

        if energy_packet.starts_below_level(last.end) or energy_packet.contact_with(last):
            last.energy += energy_packet.energy
            return self

        self.dq.append(energy_packet)

        return self

    def append_packet_left(self, energy_packet: EnergyPacket) -> 'EnergyPacketLane':
        """
        Left-append with canonicalization:
          - absorb any head packets with lower start
          - absorb any head packets that touch/overlap energy_packet after it grows
        """

        # absorb packets starting below energy_packet.start
        while self.dq and (self.dq[0].start + EPS < energy_packet.start):
            lower = self.dq.popleft()
            energy_packet.energy += lower.energy

        # absorb packets that now touch/overlap energy_packet
        while self.dq and energy_packet.overlaps_with(self.dq[0]):
            nxt = self.dq.popleft()
            energy_packet.energy += nxt.energy

        # safety: must not leave a strict overlap at the boundary
        if self.dq and energy_packet.overlaps_strictly_with(self.dq[0]):
            raise PacketOverlapError(f"Left append left strict overlap remained: energy_packet={energy_packet}, next={self.dq[0]}")

        self.dq.appendleft(energy_packet)

        return self

    def lift_front_to(self, level: float) -> 'EnergyPacketLane':
        """
        Pop head, raise to `level` if needed, insert left again.
        """
        if not self.dq:
            return self
        head = self.dq[0]
        if head.start + EPS < level:
            head = self.pop_left()
            head.lift_to(level)
            self.append_packet_left(head)
        return self


@dataclass
class PhasePair:
    """ A phase pair consists of excess energy packets and deficit energy packets belonging to exaxtly one excess phase and one deficit phase.
    """
    index_phase: int

    energy_packets: Dict[PacketType, EnergyPacketLane] = field(
        default_factory=lambda: {
            tp: EnergyPacketLane(lane_type=tp) for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED)
        }
    )

    energy_excess_initial: InitVar[float | None] = None
    energy_deficit_initial: InitVar[float | None] = None

    @property
    def ID(self) -> str:
        return f'PP{self.index_phase}'

    def __post_init__(self, energy_excess_initial: float, energy_deficit_initial: float):
        self.append_packet(
            packet_type=PacketType.EXCESS,
            energy_packet=EnergyPacket(capacity=0, energy=energy_excess_initial)
        )
        self.append_packet(
            packet_type=PacketType.DEFICIT,
            energy_packet=EnergyPacket(capacity=0, energy=energy_deficit_initial)
        )

    @property
    def n_packets(self):
        @dataclass(frozen=True)
        class nPackets:
            n_packets_excess: int
            n_packets_deficit: int
            n_packets_balanced: int

            def __getitem__(self, item) -> int:
                match item:
                    case PacketType.EXCESS:
                        return self.n_packets_excess
                    case PacketType.DEFICIT:
                        return self.n_packets_deficit
                    case PacketType.BALANCED:
                        return self.n_packets_balanced

                return 0

        return nPackets(
            n_packets_excess = self.n_packets_excess,
            n_packets_deficit = self.n_packets_deficit,
            n_packets_balanced = self.n_packets_balanced
        )

    @property
    def n_packets_excess(self):
        return len(self.energy_packets[PacketType.EXCESS])

    @property
    def n_packets_deficit(self):
        return len(self.energy_packets[PacketType.DEFICIT])

    @property
    def n_packets_balanced(self):
        return len(self.energy_packets[PacketType.BALANCED])

    @property
    def phase_type(self):
        if self.n_packets_excess == 0 and self.n_packets_deficit == 0:
            return PacketType.BALANCED

        if self.n_packets_excess >= 1 and self.n_packets_deficit >= 1:
            return PacketType.UNDEFINED

        if self.n_packets_excess >= 1:
            return PacketType.EXCESS

        if self.n_packets_deficit >= 1:
            return PacketType.DEFICIT

        raise ValueError(f'PhaseType cannot be resolved!')

    @property
    def N_unbalanced_total(self) -> int:
        return self.n_packets_excess + self.n_packets_deficit


    def _tail_capacity_max(self, packet_type: PacketType) -> float:
        lane = self.energy_packets[packet_type]
        tail = lane.peek_right()
        return tail.capacity_max if tail else float("-inf")


    def _balanced_top(self) -> float:
        return self._tail_capacity_max(PacketType.BALANCED)


    def lift_head_to(self, packet_type: PacketType, level: float) -> None:
        self.energy_packets[packet_type].lift_front_to(level)


    def enforce_above_balanced(self, energy_packet: EnergyPacket):
        # enforce "above balanced top" (if required)
        top_blc = self._balanced_top()
        energy_packet.lift_to(top_blc)
        return energy_packet


    def append_packet_left(self, packet_type: PacketType, energy_packet: EnergyPacket):
        """
        Append a packet of a given type to the left of the appropriate list.
        Asserts that the packet will conserve the canonical order of capacities compared to the BALANCED one and the list of same type.
        """
        # enforce "above balanced top" (if required)
        energy_packet = self.enforce_above_balanced(energy_packet)
        # canonicalization happens in the lane (absorbs lower-start & overlaps)
        self.energy_packets[packet_type].append_packet_left(energy_packet)


    def append_packet(self, packet_type: PacketType, energy_packet: EnergyPacket ):
        """
        Append a packet of a given type to the appropriate list.
        It will ensure the canonical order of capacities within the list of the same type.
        All packets have to be at least as high as the top of the highest BALANCED packet.
        When a packet has the same or a lower capacity and its capacity has to be increased, it will merge with the topmost packet.
        """

        # enforce "above balanced top"
        energy_packet = self.enforce_above_balanced(energy_packet)
        # lane enforces: merge touching or lower
        self.energy_packets[packet_type].append_packet(energy_packet)


    def pop_packet_left(self, packet_type: PacketType):
        """
        Will pop the first packet of a given type.
        """
        return self.energy_packets[packet_type].pop_left()


    def pop_packet(self, packet_type: PacketType):
        """
        Will pop the last packet of a given type.
        """
        return self.energy_packets[packet_type].pop_right()


    def balance(self):
        while self.phase_type == PacketType.UNDEFINED:
            self.balance_first_packet()


    def balance_first_packet(self):
        """
        Take the first packets of the EXCESS and DEFICIT type, determines the residual, adds the BALANCED part and puts the residual back into the appropriate deque.
        """

        energy_packet_exs = self.energy_packets[PacketType.EXCESS].pop_left()
        energy_packet_def = self.energy_packets[PacketType.DEFICIT].pop_left()

        # 1. Align Capacities (Lift the lower one to the higher one)
        capacity_bottom = max(energy_packet_exs.capacity, energy_packet_def.capacity)
        energy_packet_exs = energy_packet_exs.lift_to(capacity_bottom)
        energy_packet_def = energy_packet_def.lift_to(capacity_bottom)

        # 2. Calculate Energy Difference
        # diff > 0: Deficit is larger (Residual is Deficit)
        # diff < 0: Excess is larger (Residual is Excess)
        diff = energy_packet_def.energy - energy_packet_exs.energy

        # 4. Create Balanced Packet (using the Deficit packet as container)
        # The balanced amount is the min energy of both.
        energy_balanced = min(energy_packet_exs.energy, energy_packet_def.energy)
        energy_packet_bal = energy_packet_def
        # 3. Handle Residuals
        if diff > EPS:
            # Deficit was larger; Excess is fully consumed.
            # We need to put the remaining Deficit back.
            # We can create a new packet or reuse energy_packet_exs if we wanted,
            # but creating new for residual is cleaner for ownership.
            energy_packet_def.energy = diff
            energy_packet_def.lift_to(energy_packet_exs.capacity_max)
            self.energy_packets[PacketType.DEFICIT].append_packet_left(energy_packet_def)
            energy_packet_bal = energy_packet_exs
        elif diff < -EPS:
            # Excess was larger; Deficit is fully consumed.
            energy_packet_exs.energy = -diff
            energy_packet_exs.lift_to(energy_packet_def.capacity_max)
            self.energy_packets[PacketType.EXCESS].append_packet_left(energy_packet_exs)

        self.energy_packets[PacketType.BALANCED].append_packet(energy_packet_bal)


@dataclass
class ShiftInput:
    index: int|None
    capacity_hurdle: float


@dataclass
class PhaseGroup:
    """
    A phase-group is collection of phase-pairs that can be compressed, balanced, and combined with other phase groups.
    A phase-group of type UNDEFINED will need to be balanced first and will then be either EXCESS, DEFICIT, or BALANCED.
    Phase-groups of type EXCESS or DEFICIT can be compressed by shifting the energy packets of the grouped phase pairs.
    """

    group_type: PacketType
    index_start: int
    index_end: int = None

    shift_inputs: List[ShiftInput] = field(default_factory=list)

    _merge_rules = {
        (PacketType.UNDEFINED, PacketType.UNDEFINED): (None, "This needs to undergo balance first."),
        (PacketType.UNDEFINED, PacketType.BALANCED) : (None, "This needs to undergo balance first."),
        (PacketType.UNDEFINED, PacketType.EXCESS)   : (None, "This needs to undergo balance first."),
        (PacketType.UNDEFINED, PacketType.DEFICIT)  : (None, "This needs to undergo balance first."),
        (PacketType.BALANCED,  PacketType.UNDEFINED): (None, "This needs to undergo balance first."),
        (PacketType.EXCESS,    PacketType.UNDEFINED): (None, "This needs to undergo balance first."),
        (PacketType.DEFICIT,   PacketType.UNDEFINED): (None, "This needs to undergo balance first."),

        (PacketType.BALANCED,  PacketType.BALANCED) : (PacketType.BALANCED, "Same type"),
        (PacketType.EXCESS,    PacketType.EXCESS)   : (PacketType.EXCESS, "Same type"),
        (PacketType.DEFICIT,   PacketType.DEFICIT)  : (PacketType.DEFICIT, "Same type"),

        (PacketType.BALANCED,  PacketType.DEFICIT)  : (PacketType.DEFICIT, "DEFICIT will be shifted left over BALANCE."),
        (PacketType.EXCESS,    PacketType.BALANCED) : (PacketType.EXCESS,"EXCESS will be shifted right over BALANCE."),

        (PacketType.BALANCED,  PacketType.EXCESS)   : (None, "We would loose information for potential later shift operations."),
        (PacketType.DEFICIT,   PacketType.BALANCED) : (None, "We would loose information for potential later shift operations."),

        (PacketType.EXCESS,    PacketType.DEFICIT)  : (None, "This needs to undergo shifting first."),
        (PacketType.DEFICIT,   PacketType.EXCESS)   : (None, "This needs to undergo shifting first."),
    }


    @property
    def ID(self) -> str:
        s = f'PG {self.index_start}'
        if self.index_start != self.index_end:
            s += f'..{self.index_end}'

        s += f' {self.group_type.name[0:3]}'
        return s


    def balance(self, ctx: 'Context'):
        """
        Balancing a group is only required for group_type==UNDEFINED and will only need to check the very first phase pair at index_start.
        """
        if self.group_type == PacketType.BALANCED:
            return

        if self.group_type == PacketType.DEFICIT or self.group_type == PacketType.EXCESS:
            raise ValueError(f'[{self.ID}] A group of type {self.group_type.name} cannot be balanced!')

        phase_pair = ctx.phase_pairs[self.index_start]

        phase_pair.balance()

        self.group_type = ctx.phase_pairs[self.index_start].phase_type


        if self.group_type == PacketType.BALANCED:
            self.shift_inputs = [ShiftInput(
                index=None,
                capacity_hurdle=ctx.phase_pairs[self.index_start].energy_packets[PacketType.BALANCED].peek_right().capacity_max
            )]
        else:
            self.shift_inputs = [ShiftInput(
                index=self.index_start,
                capacity_hurdle=0
            )]


    def can_merge(self, other: 'PhaseGroup') -> bool:
        return PhaseGroup._merge_rules[(self.group_type, other.group_type)][0] is not None


    def merge_with(self, other: 'PhaseGroup'):

        new_type, reason = PhaseGroup._merge_rules[(self.group_type, other.group_type)]

        if new_type is None:
            return False, reason

        self.group_type = new_type

        """Merging two groups will allways set the end index of the first one to the end index of the second one."""
        self.index_end = other.index_end

        if self.group_type != PacketType.BALANCED or other.group_type != PacketType.BALANCED:
            self.shift_inputs.extend(other.shift_inputs)
        elif len(other.shift_inputs) != 0: # If both groups are BALANCED, we only keep the higher capacity and do not extend the shift inputs

            if len(self.shift_inputs) == 0:
                self.shift_inputs.extend(other.shift_inputs)
            elif self.shift_inputs[-1].capacity_hurdle < other.shift_inputs[-1].capacity_hurdle + EPS:
                self.shift_inputs[-1].capacity_hurdle = other.shift_inputs[-1].capacity_hurdle

        return True, reason


    def get_shift_target_index(self, ctx: 'Context'):
        return self.index_start if self.group_type == PacketType.DEFICIT else (self.index_end + 1) % ctx.N_phase_pairs


    def _shift_one_from_to(self, phase_pair_source:PhasePair, phase_pair_target:PhasePair, capacity_hurdle:float):
        energy_packet = phase_pair_source.pop_packet_left(self.group_type)

        if energy_packet.starts_below_level(capacity_hurdle):
            energy_packet.lift_to(capacity_hurdle)

        phase_pair_target.append_packet(self.group_type, energy_packet)


    def _shift_all_from_to(self, phase_pair_source:PhasePair, phase_pair_target:PhasePair, capacity_hurdle:float):
        while phase_pair_source.n_packets[self.group_type] > 0:
            self._shift_one_from_to(phase_pair_source, phase_pair_target, capacity_hurdle)


    def _apply_shift_input(self, phase_pair_target:PhasePair, capacity_hurdle:float, shift_input: ShiftInput, ctx: 'Context' ) -> float:
        index = shift_input.index
        index_target = phase_pair_target.index_phase

        # hurdle must include BALANCED entries too
        if capacity_hurdle < shift_input.capacity_hurdle:
            capacity_hurdle = shift_input.capacity_hurdle

        if index is None or index == index_target:
            # Nothing to shift from a BALANCED index or same index
            return capacity_hurdle

        phase_pair_source = ctx.phase_pairs[index]

        self._shift_all_from_to(phase_pair_source, phase_pair_target, capacity_hurdle)
        return capacity_hurdle


    def shift(self, ctx: 'Context'):
        """
        For EXCESS groups we iterate over the indices and capacities in reverse direction and shift the to start of the next group.
        """
        assert self.group_type != PacketType.UNDEFINED, f'[{self.ID}] Cannot shift UNDEFINED group!'

        if self.group_type == PacketType.BALANCED or (self.group_type == PacketType.DEFICIT and self.index_start == self.index_end):
            if self.group_type == PacketType.DEFICIT:
                self.group_type = PacketType.UNDEFINED
                self.shift_inputs = []
            return

        # shift to the start of the same group for DEFICIT and to the start of the next group for EXCESS
        index_target = self.get_shift_target_index(ctx)
        phase_pair_target =  ctx.phase_pairs[index_target]

        capacity_hurdle = 0.0

        # iterate forward for DEFICIT and backward for EXCESS
        shift_inputs = self.shift_inputs if self.group_type == PacketType.DEFICIT else reversed(self.shift_inputs)

        for shift_input in shift_inputs:
            capacity_hurdle = self._apply_shift_input(
                phase_pair_target=phase_pair_target,
                shift_input=shift_input,
                capacity_hurdle=capacity_hurdle,
                ctx=ctx,
            )

        self.group_type = PacketType.UNDEFINED if self.group_type == PacketType.DEFICIT else PacketType.BALANCED
        self.shift_inputs = []
        return



@dataclass
class Context:
    energy_excess_per_phase_initial: List[float]
    energy_deficit_per_phase_initial: List[float]

    phase_pairs: List[PhasePair] = None  # The algorithm will store results in this one

    phase_groups: Deque[PhaseGroup] = None  # The algorithm will work on this one

    n_iterations:int = 0

    @property
    def ID(self):
        return 'mEfES context'

    @property
    def done(self):
        excess_remaining = False
        deficit_remaining = False
        for phase_pair in self.phase_pairs:
            if not excess_remaining and len(phase_pair.energy_packets[PacketType.EXCESS]):
                excess_remaining = True

            if not deficit_remaining and len(phase_pair.energy_packets[PacketType.DEFICIT]):
                deficit_remaining = True

            if excess_remaining and deficit_remaining:
                return False

        return True

    @property
    def N_unbalanced_total(self):
        return sum([phase_pair.N_unbalanced_total for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_excess(self):
        return sum([phase_pair.n_packets_excess for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_deficit(self):
        return sum([phase_pair.n_packets_deficit for phase_pair in self.phase_pairs])

    @property
    def N_phases(self):
        return 2*len(self.energy_deficit_per_phase_initial)

    @property
    def N_phase_pairs(self):
        return len(self.energy_deficit_per_phase_initial)

    @property
    def N_phase_groups(self):
        return len(self.phase_groups)


    def __post_init__(self):
        assert len(self.energy_excess_per_phase_initial) == len(self.energy_deficit_per_phase_initial)

        self.phase_pairs = [PhasePair(
            index_phase=ix,
            energy_excess_initial=energy_excess_initial,
            energy_deficit_initial=energy_deficit_initial,
        ) for ix, (energy_excess_initial, energy_deficit_initial) in enumerate(zip(self.energy_excess_per_phase_initial, self.energy_deficit_per_phase_initial))]

        self.phase_groups = deque([PhaseGroup(
            group_type=PacketType.UNDEFINED,  # A phase-group of type UNDEFINED will need to be balanced first and will then be either EXCESS, DEFICIT, or BALANCED
            index_start=index_phase,
            index_end=index_phase
        ) for index_phase in range(self.N_phase_pairs)])


    def balance(self):
        assert not self.done
        for phase_group in self.phase_groups:
            phase_group.balance(self)


    def _merge_end_of_stack(self, stack: Deque[PhaseGroup]) -> Deque[PhaseGroup]:
        # reduce as long as the last two are mergeable
        while len(stack) >= 2 and stack[-2].can_merge(stack[-1]):
            left = stack[-2]
            right = stack[-1]
            merged, reason = left.merge_with(right)

            if not merged:
                raise RuntimeError(f"can_merge True but merge_with failed: {reason}")

            stack.pop()  # remove right; left is mutated in place

        return stack


    def _stack_merge(self) -> Deque[PhaseGroup]:
        stack: Deque[PhaseGroup] = deque()

        for g in self.phase_groups:
            stack.append(g)
            self._merge_end_of_stack(stack)

        self.phase_groups = stack
        return stack


    def _boundary_merge(self) -> Deque[PhaseGroup]:
        while len(self.phase_groups) > 1 and self.phase_groups[-1].can_merge(self.phase_groups[0]):
            left = self.phase_groups[-1]  # last
            right = self.phase_groups[0]  # first
            merged, reason = left.merge_with(right)
            if not merged:
                raise RuntimeError(f"can_merge True but merge_with failed: {reason}")
            self.phase_groups.popleft()  # remove the consumed 'first'

            # After changing the tail group, it might now merge with its predecessor.
            # Reduce tail locally (like stack reduction, but only near the end).
            self._merge_end_of_stack(self.phase_groups)

        return self.phase_groups


    def merge(self) -> None:
        assert not self.done

        dq = self.phase_groups
        if len(dq) < 2:
            return

        # ---- 1) Linear reduction (treat current deque order as the cycle order)
        self._stack_merge()
        # stack is now reduced for all internal adjacencies (i,i+1)

        # ---- 2) Cyclic wrap-around reduction: repeatedly reduce (last, first)
        # Use deque for O(1) popleft.
        # While boundary pair can merge: merge last -> first (same direction as cyclic adjacency)
        self._boundary_merge()


    def shift(self):
        assert not self.done
        """Iterate over all phase_groups and shift EXCESS groups to the next DEFICIT group"""

        for grp in self.phase_groups:
            grp.shift(self)


    def run_mEfES(self):
        self.balance()
        self.n_iterations = 0
        while not self.done:
            self.n_iterations += 1
            self.merge()
            self.shift()
            self.balance()
