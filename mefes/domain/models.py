from __future__ import annotations

from collections import deque
from dataclasses import InitVar, dataclass, field
from typing import Deque, Dict, Iterator, List, Optional

from efes_core.domain.enums import PacketType
from efes_core.domain.models import EnergyPacket, AlgorithmState
from .errors import PacketLaneError, PacketOrderError, PacketOverlapError, InvariantViolation, \
    ValidationError

EPS = 1e-8


@dataclass
class EnergyPacketLane:
    lane_type: PacketType
    dq: Deque[EnergyPacket] = field(default_factory=deque)

    @property
    def id(self) -> str:
        return f"{self.lane_type.name} Lane"

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

    def append_packet(self, energy_packet: EnergyPacket, merge_packets:bool = True) -> "EnergyPacketLane":
        """
        Tail append:
        - merges touching packets
        - merges packets whose start is below the current tail end
        - otherwise appends as a new packet

        This matches the original mEfES behavior.
        """
        if not self.dq:
            self.dq.append(energy_packet)
            return self

        last = self.dq[-1]

        if energy_packet.starts_below_level(last.end) or energy_packet.contact_with(last):
            if merge_packets:
                last.energy += energy_packet.energy
                return self

            energy_packet.capacity=last.end

        self.dq.append(energy_packet)
        return self

    def append_packet_left(self, energy_packet: EnergyPacket) -> "EnergyPacketLane":
        """
        Left append with canonicalization:
        - absorb any head packets with lower start
        - absorb any head packets that touch/overlap after growth
        """
        while self.dq and (self.dq[0].start + EPS < energy_packet.start):
            lower = self.dq.popleft()
            energy_packet.energy += lower.energy

        while self.dq and energy_packet.overlaps_with(self.dq[0]):
            nxt = self.dq.popleft()
            energy_packet.energy += nxt.energy

        if self.dq and energy_packet.overlaps_strictly_with(self.dq[0]):
            raise PacketOverlapError(
                f"Left append strict overlap remained: packet={energy_packet}, next={self.dq[0]}"
            )

        self.dq.appendleft(energy_packet)
        return self

    def lift_front_to(self, level: float) -> "EnergyPacketLane":
        if not self.dq:
            return self

        head = self.dq[0]
        if head.start + EPS < level:
            head = self.pop_left()
            head.lift_to(level)
            self.append_packet_left(head)

        return self


@dataclass(frozen=True)
class PacketCounts:
    n_packets_excess: int
    n_packets_deficit: int
    n_packets_balanced: int

    def __getitem__(self, item: PacketType) -> int:
        if item == PacketType.EXCESS:
            return self.n_packets_excess
        if item == PacketType.DEFICIT:
            return self.n_packets_deficit
        if item == PacketType.BALANCED:
            return self.n_packets_balanced
        return 0


@dataclass
class PhasePair:
    index_phase: int

    energy_packets: Dict[PacketType, EnergyPacketLane] = field(
        default_factory=lambda: {
            tp: EnergyPacketLane(lane_type=tp)
            for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED)
        }
    )

    energy_excess_initial: InitVar[float | None] = None
    energy_deficit_initial: InitVar[float | None] = None

    @property
    def id(self) -> str:
        return f"PP{self.index_phase}"

    def __post_init__(
        self,
        energy_excess_initial: float | None,
        energy_deficit_initial: float | None,
    ) -> None:
        if energy_excess_initial is not None:
            self.append_packet(
                packet_type=PacketType.EXCESS,
                energy_packet=EnergyPacket(capacity=0, energy=energy_excess_initial),
            )

        if energy_deficit_initial is not None:
            self.append_packet(
                packet_type=PacketType.DEFICIT,
                energy_packet=EnergyPacket(capacity=0, energy=energy_deficit_initial),
            )

    @property
    def n_packets(self) -> PacketCounts:
        return PacketCounts(
            n_packets_excess=self.n_packets_excess,
            n_packets_deficit=self.n_packets_deficit,
            n_packets_balanced=self.n_packets_balanced,
        )

    @property
    def n_packets_excess(self) -> int:
        return len(self.energy_packets[PacketType.EXCESS])

    @property
    def n_packets_deficit(self) -> int:
        return len(self.energy_packets[PacketType.DEFICIT])

    @property
    def n_packets_balanced(self) -> int:
        return len(self.energy_packets[PacketType.BALANCED])

    @property
    def phase_type(self) -> PacketType:
        if self.n_packets_excess == 0 and self.n_packets_deficit == 0:
            return PacketType.BALANCED
        if self.n_packets_excess >= 1 and self.n_packets_deficit >= 1:
            return PacketType.UNDEFINED
        if self.n_packets_excess >= 1:
            return PacketType.EXCESS
        if self.n_packets_deficit >= 1:
            return PacketType.DEFICIT
        raise InvariantViolation("Phase type cannot be resolved.")

    @property
    def n_unbalanced_total(self) -> int:
        return self.n_packets_excess + self.n_packets_deficit

    def _tail_capacity_max(self, packet_type: PacketType) -> float:
        lane = self.energy_packets[packet_type]
        tail = lane.peek_right()
        return tail.capacity_max if tail else float("-inf")

    def balanced_top(self) -> float:
        return self._tail_capacity_max(PacketType.BALANCED)

    def lift_head_to(self, packet_type: PacketType, level: float) -> None:
        self.energy_packets[packet_type].lift_front_to(level)

    def enforce_above_balanced(self, energy_packet: EnergyPacket) -> EnergyPacket:
        energy_packet.lift_to(self.balanced_top())
        return energy_packet

    def append_packet_left(
        self,
        packet_type: PacketType,
        energy_packet: EnergyPacket,
    ) -> None:
        energy_packet = self.enforce_above_balanced(energy_packet)
        self.energy_packets[packet_type].append_packet_left(energy_packet)

    def append_packet(
        self,
        packet_type: PacketType,
        energy_packet: EnergyPacket,
    ) -> None:
        energy_packet = self.enforce_above_balanced(energy_packet)
        self.energy_packets[packet_type].append_packet(energy_packet)

    def pop_packet_left(self, packet_type: PacketType) -> EnergyPacket:
        return self.energy_packets[packet_type].pop_left()

    def pop_packet(self, packet_type: PacketType) -> EnergyPacket:
        return self.energy_packets[packet_type].pop_right()


@dataclass(frozen=True)
class ShiftInput:
    index: int | None
    capacity_hurdle: float


@dataclass
class PhaseGroup:
    """
    Pure domain model for a group of adjacent phase pairs.
    The merge and shift orchestration should live in the application/use-case layer.
    """

    group_type: PacketType
    index_start: int
    index_end: int | None = None
    shift_inputs: List[ShiftInput] = field(default_factory=list)

    _merge_rules = {
        (PacketType.UNDEFINED, PacketType.UNDEFINED): (None, "Balance first."),
        (PacketType.UNDEFINED, PacketType.BALANCED): (None, "Balance first."),
        (PacketType.UNDEFINED, PacketType.EXCESS): (None, "Balance first."),
        (PacketType.UNDEFINED, PacketType.DEFICIT): (None, "Balance first."),
        (PacketType.BALANCED, PacketType.UNDEFINED): (None, "Balance first."),
        (PacketType.EXCESS, PacketType.UNDEFINED): (None, "Balance first."),
        (PacketType.DEFICIT, PacketType.UNDEFINED): (None, "Balance first."),
        (PacketType.BALANCED, PacketType.BALANCED): (PacketType.BALANCED, "Same type"),
        (PacketType.EXCESS, PacketType.EXCESS): (PacketType.EXCESS, "Same type"),
        (PacketType.DEFICIT, PacketType.DEFICIT): (PacketType.DEFICIT, "Same type"),
        (PacketType.BALANCED, PacketType.DEFICIT): (
            PacketType.DEFICIT,
            "DEFICIT shifts left over BALANCED.",
        ),
        (PacketType.EXCESS, PacketType.BALANCED): (
            PacketType.EXCESS,
            "EXCESS shifts right over BALANCED.",
        ),
        (PacketType.BALANCED, PacketType.EXCESS): (
            None,
            "Would lose information for later shift operations.",
        ),
        (PacketType.DEFICIT, PacketType.BALANCED): (
            None,
            "Would lose information for later shift operations.",
        ),
        (PacketType.EXCESS, PacketType.DEFICIT): (None, "Shift first."),
        (PacketType.DEFICIT, PacketType.EXCESS): (None, "Shift first."),
    }

    def __post_init__(self) -> None:
        if self.index_end is None:
            self.index_end = self.index_start

    @property
    def id(self) -> str:
        s = f"PG {self.index_start}"
        if self.index_start != self.index_end:
            s += f"..{self.index_end}"
        s += f" {self.group_type.name[:3]}"
        return s

    def can_merge(self, other: "PhaseGroup") -> bool:
        return self._merge_rules[(self.group_type, other.group_type)][0] is not None

    def merge_with(self, other: "PhaseGroup") -> tuple[bool, str]:
        new_type, reason = self._merge_rules[(self.group_type, other.group_type)]

        if new_type is None:
            return False, reason

        self.group_type = new_type
        self.index_end = other.index_end

        if self.group_type != PacketType.BALANCED or other.group_type != PacketType.BALANCED:
            self.shift_inputs.extend(other.shift_inputs)
        elif other.shift_inputs:
            if not self.shift_inputs:
                self.shift_inputs.extend(other.shift_inputs)
            elif (
                self.shift_inputs[-1].capacity_hurdle
                < other.shift_inputs[-1].capacity_hurdle + EPS
            ):
                self.shift_inputs[-1] = ShiftInput(
                    index=self.shift_inputs[-1].index,
                    capacity_hurdle=other.shift_inputs[-1].capacity_hurdle,
                )

        return True, reason


@dataclass
class MefesState(AlgorithmState):
    """
    State container only.
    Algorithmic orchestration belongs in an application service / use case.
    """

    energy_excess_per_phase_initial: List[float] = None
    energy_deficit_per_phase_initial: List[float] = None

    phase_pairs: List[PhasePair] = field(default_factory=list)
    phase_groups: Deque[PhaseGroup] = field(default_factory=deque)
    n_iterations: int = 0

    @property
    def id(self) -> str:
        return "mEfES state"

    @property
    def done(self) -> bool:
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
    def n_unbalanced_total(self) -> int:
        return sum(phase_pair.n_unbalanced_total for phase_pair in self.phase_pairs)

    @property
    def n_unbalanced_excess(self) -> int:
        return sum(phase_pair.n_packets_excess for phase_pair in self.phase_pairs)

    @property
    def n_unbalanced_deficit(self) -> int:
        return sum(phase_pair.n_packets_deficit for phase_pair in self.phase_pairs)

    @property
    def n_phases(self) -> int:
        return 2 * len(self.energy_deficit_per_phase_initial)

    @property
    def n_phase_pairs(self) -> int:
        return len(self.energy_deficit_per_phase_initial)

    @property
    def n_phase_groups(self) -> int:
        return len(self.phase_groups)

    def initialize(self) -> None:
        if self.energy_excess_per_phase_initial is None or self.energy_deficit_per_phase_initial is None:
            raise ValidationError("The mEfES state does not have energy values per phase.")

        if len(self.energy_excess_per_phase_initial) != len(self.energy_deficit_per_phase_initial):
            raise ValidationError(
                "energy_excess_per_phase_initial and energy_deficit_per_phase_initial "
                "must have the same length."
            )

        self.phase_pairs = [
            PhasePair(
                index_phase=ix,
                energy_excess_initial=energy_excess_initial,
                energy_deficit_initial=energy_deficit_initial,
            )
            for ix, (energy_excess_initial, energy_deficit_initial) in enumerate(
                zip(
                    self.energy_excess_per_phase_initial,
                    self.energy_deficit_per_phase_initial,
                )
            )
        ]

        self.phase_groups = deque(
            PhaseGroup(
                group_type=PacketType.UNDEFINED,
                index_start=index_phase,
                index_end=index_phase,
            )
            for index_phase in range(self.n_phase_pairs)
        )