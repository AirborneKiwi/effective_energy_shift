from __future__ import annotations

import random
from functools import wraps

from enum import IntEnum, Enum, auto
from collections import deque, defaultdict
from dataclasses import dataclass, field, InitVar
from os import times_result

from typing import Deque, List, Set, Dict, Tuple, Iterable, Optional, Iterator
from typing import Callable, TypeVar, ParamSpec, cast
from warnings import deprecated

EPS = 1e-8

P = ParamSpec("P")
R = TypeVar("R")

# Toggle at import-time / runtime.
CHECK_INVARIANTS = True
DEBUG_LOG = False
REC_EVTS = False


class EventType(Enum):
    APPEND_EXCESS = auto(),
    APPEND_DEFICIT = auto(),
    APPEND_BALANCED = auto(),

    APPEND_LEFT_EXCESS = auto(),
    APPEND_LEFT_DEFICIT = auto(),
    APPEND_LEFT_BALANCED = auto(),

    POP_EXCESS = auto(),
    POP_DEFICIT = auto(),
    POP_BALANCED = auto(),

    POP_LEFT_EXCESS = auto(),
    POP_LEFT_DEFICIT = auto(),
    POP_LEFT_BALANCED = auto(),

    NEXT_ITERATION = auto(),

    BALANCE_STEP = auto(),

    BALANCE_GROUP = auto(),
    BALANCE_OBSOLETE = auto(),

    EXCESS_BELOW_DEFICIT = auto(),
    DEFICIT_BELOW_EXCESS = auto(),

    EXCESS_REMAINING = auto(),
    DEFICIT_REMAINING = auto(),
    BALANCED_PHASE = auto(),

    BALANCED_ABSORBED_AT_TOP = auto(),
    BALANCED_ABSORBED_AT_FRONT = auto(),
    BALANCED_HOVERS_AT_TOP = auto(),
    BALANCED_HOVERS_AT_BOTTOM = auto(),

    EXCESS_ABSORBED_AT_TOP = auto(),
    EXCESS_ABSORBED_AT_FONT = auto(),
    EXCESS_HOVERS_AT_TOP = auto(),
    EXCESS_HOVERS_AT_BOTTOM = auto(),

    DEFICIT_ABSORBED_AT_TOP = auto(),
    DEFICIT_ABSORBED_AT_FRONT = auto(),
    DEFICIT_HOVERS_AT_TOP = auto(),
    DEFICIT_HOVERS_AT_BOTTOM = auto(),

    EXCESS_RAISED_TO_BALANCED_TOP = auto(),
    DEFICIT_RAISED_TO_BALANCED_TOP = auto(),
    BALANCED_RAISED_TO_BALANCED_TOP = auto(),

    BALANCE_CREATES_HURDLE = auto(),

    SHIFT_STEP = auto(),

    SHIFT_GROUP = auto(),
    SHIFT_GROUP_OBSOLETE = auto(),

    SHIFT_PACKET_EXCESS = auto(),
    SHIFT_PACKET_DEFICIT = auto(),
    HURDLE_JUMP_BY_EXCESS = auto(),
    HURDLE_JUMP_BY_DEFICIT = auto(),

    MERGE_STEP = auto(),

    MERGE_EXC_EXC = auto(),
    MERGE_DEF_DEF = auto(),
    MERGE_BAL_BAL = auto(),
    MERGE_BAL_DEF = auto(),
    MERGE_EXC_BAL = auto(),

    MERGE_REJECTED_UND = auto(),
    MERGE_REJECTED_EXC_DEF = auto(),
    MERGE_REJECTED_DEF_EXC = auto(),

    MERGE_REJECTED_BAL_EXC = auto(),
    MERGE_REJECTED_DEF_BAL = auto(),


@dataclass
class Event:
    evt_type: str | EventType
    triggered_by:str
    id:int = None


class EventRecorder:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is  None:
            cls._instance = cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # IMPORTANT: __init__ will run on every call unless guarded
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.observed_events: Dict[str, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order: List[Event] = []
        self.n_observed_events: int = 0


    def reset(self):
        self.observed_events: Dict[str, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order: List[Event] = []
        self.n_observed_events: int = 0


    def record(self, event: Event):
        if isinstance(event.evt_type, EventType):
            event.evt_type = event.evt_type.name

        if event.evt_type not in self.observed_events:
            self.observed_events[event.evt_type] = []

        event.id = self.n_observed_events
        self.observed_events[event.evt_type].append(event)
        self.n_observed_events += 1

        self.observed_events_in_order.append(event)

        if DEBUG_LOG:
            print(f'Event {event.evt_type} triggered by {event.triggered_by}')


    def print_events(self, group_by_type:bool=True, show_all=False, print_trace:bool=False):
        return self.__str__(group_by_type=group_by_type, show_all=show_all, print_trace=print_trace)


    def __str__(self, group_by_type:bool=True, show_all=False, print_trace:bool=False):
        s = ''
        if group_by_type:
            for event_type, events in self.observed_events.items():
                if len(events) > 0 or show_all:
                    s += f'{len(events)} x {event_type} by {[event.triggered_by for event in events]} \n'
            s += '\n---------------------------\n'

        # print in id order
        if print_trace:
            for event in self.observed_events_in_order:
                s += f'{event.evt_type} by {event.triggered_by} \n'

            s += '\n---------------------------\n'
        return s



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


    def rec_evt(self, evt_type: str|EventType):
        EventRecorder().record(Event(evt_type=evt_type, triggered_by=self.ID))


    def __len__(self) -> int:
        return len(self.dq)

    def __iter__(self) -> Iterator[EnergyPacket]:
        return iter(self.dq)

    def peek_left(self) -> Optional[EnergyPacket]:
        return self.dq[0] if self.dq else None

    def peek_right(self) -> Optional[EnergyPacket]:
        return self.dq[-1] if self.dq else None

    @staticmethod
    def _log_pop_left(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)

            if DEBUG_LOG:
                print(f'[{self.ID}] First {self.lane_type.name} packet removed. New packet count is {len(self)}')

            return res

        return wrapper

    @staticmethod
    def _rec_evt_pop_left(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)

            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.POP_LEFT_EXCESS,
                    PacketType.DEFICIT: EventType.POP_LEFT_DEFICIT,
                    PacketType.BALANCED: EventType.POP_LEFT_BALANCED,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            return res

        return wrapper

    @_rec_evt_pop_left
    @_log_pop_left
    def pop_left(self) -> EnergyPacket:
        return self.dq.popleft()


    @staticmethod
    def _log_pop_right(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)

            if DEBUG_LOG:
                print(f'[{self.ID}] Last {self.lane_type.name} packet removed. New packet count is {len(self)}')

            return res

        return wrapper

    @staticmethod
    def _rec_evt_pop_right(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)

            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.POP_RIGHT_EXCESS,
                    PacketType.DEFICIT: EventType.POP_RIGHT_DEFICIT,
                    PacketType.BALANCED: EventType.POP_RIGHT_BALANCED,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            return res

        return wrapper

    @_rec_evt_pop_right
    @_log_pop_right
    def pop_right(self) -> EnergyPacket:
        return self.dq.pop()


    @staticmethod
    def _log_append_packet(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, pkt: EnergyPacket, *args, **kwargs):
            if DEBUG_LOG:
                print(f'[{self.ID}] Appending packet: {pkt}')

            res = func(self, pkt, *args, **kwargs)

            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_TOP,
                    PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_TOP,
                    PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_TOP,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            return res

        return wrapper

    @staticmethod
    def _rec_evt_append_packet(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, pkt: EnergyPacket, *args, **kwargs):
            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.APPEND_EXCESS,
                    PacketType.DEFICIT: EventType.APPEND_DEFICIT,
                    PacketType.BALANCED: EventType.APPEND_BALANCED,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            res = func(self, pkt, *args, **kwargs)

            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_TOP,
                    PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_TOP,
                    PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_TOP,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            return res

        return wrapper

    @_rec_evt_append_packet
    @_log_append_packet
    def append_packet(self, pkt: EnergyPacket) -> 'EnergyPacketLane':
        """
        Tail-append:
          - merges touching (within EPS)
          - raises on strict overlap
          - raises if start order goes backwards
        """
        if not self.dq:
            self.dq.append(pkt)
            return self

        last = self.dq[-1]

        #if pkt.start + EPS < last.end:
        #    pkt.start = last.start
            #raise PacketOrderError(f"Tail append out-of-order: {pkt.start} < {last.start}")

        #if last.overlaps_strictly_with(pkt):
            #raise PacketOverlapError(f"Tail append strict overlap: last={last}, pkt={pkt}")

        if pkt.starts_below_level(last.end) or pkt.contact_with(last):
            last.energy += pkt.energy
            return self

        self.dq.append(pkt)

        return self

    @staticmethod
    def _log_append_packet_left(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, pkt: EnergyPacket, *args, **kwargs):
            if DEBUG_LOG:
                print(f'[{self.ID}] Appending packet left: {pkt}')
            res = func(self, pkt, *args, **kwargs)
            if DEBUG_LOG:
                print(f'[{self.ID}] Packet appended left. New packet count is {len(self)}')
            return res

        return wrapper

    @staticmethod
    def _rec_evt_append_packet_left(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, pkt: EnergyPacket, *args, **kwargs):
            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.APPEND_LEFT_EXCESS,
                    PacketType.DEFICIT: EventType.APPEND_LEFT_DEFICIT,
                    PacketType.BALANCED: EventType.APPEND_LEFT_BALANCED,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            res = func(self, pkt, *args, **kwargs)

            if REC_EVTS:
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_BOTTOM,
                    PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_BOTTOM,
                    PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_BOTTOM,
                }
                self.rec_evt(evt_type_mapping[self.lane_type])

            return res

        return wrapper

    @_rec_evt_append_packet_left
    @_log_append_packet_left
    def append_packet_left(self, pkt: EnergyPacket) -> 'EnergyPacketLane':
        """
        Left-append with canonicalization:
          - absorb any head packets with lower start
          - absorb any head packets that touch/overlap pkt after it grows
        """

        # absorb packets starting below pkt.start
        while self.dq and (self.dq[0].start + EPS < pkt.start):
            lower = self.dq.popleft()
            pkt.energy += lower.energy

        # absorb packets that now touch/overlap pkt
        while self.dq and pkt.overlaps_with(self.dq[0]):
            nxt = self.dq.popleft()
            pkt.energy += nxt.energy

        # safety: must not leave a strict overlap at the boundary
        if self.dq and pkt.overlaps_strictly_with(self.dq[0]):
            raise PacketOverlapError(f"Left append left strict overlap remained: pkt={pkt}, next={self.dq[0]}")

        self.dq.appendleft(pkt)

        return self

    @staticmethod
    def _log_lift_front_to(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, level: float, *args, **kwargs):
            if DEBUG_LOG:
                print(f'[{self.ID}] Lift request to {level}')

            res = func(self, level, *args, **kwargs)
            return res

        return wrapper

    @_log_lift_front_to
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


def phasepair_invariants(method: Callable[P, R]) -> Callable[P, R]:
    """
    Minimal decorator for PhasePair instance methods.

    - If CHECK_INVARIANTS is False, returns the original method unchanged (no wrapper).
    - If CHECK_INVARIANTS is True, wraps the method and calls self._check_invariants()
      after successful execution.

    Notes:
    - Assumes the decorated method is a bound PhasePair method (self is first arg).
    - Post-check only (no pre-check), as requested.
    """

    if not (__debug__ and CHECK_INVARIANTS):
        return method  # no wrapping at all

    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        result = method(*args, **kwargs)
        self_obj = args[0]
        # Expect PhasePair-like object with _check_invariants()
        self_obj._check_invariants()
        return result

    return cast(Callable[P, R], wrapped)


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

    def rec_evt(self, evt_type: str|EventType):
        EventRecorder().record(Event(evt_type=evt_type, triggered_by=self.ID))

    @property
    def ID(self) -> str:
        return f'PP{self.index_phase}'

    def __post_init__(self, energy_excess_initial: float, energy_deficit_initial: float):
        global DEBUG_LOG
        _tmp_debug_log = DEBUG_LOG
        DEBUG_LOG = False

        self.append_packet(
            packet_type=PacketType.EXCESS,
            energy_packet=EnergyPacket(capacity=0, energy=energy_excess_initial)
        )
        self.append_packet(
            packet_type=PacketType.DEFICIT,
            energy_packet=EnergyPacket(capacity=0, energy=energy_deficit_initial)
        )
        DEBUG_LOG = _tmp_debug_log


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

    def _check_invariants(self):
        for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED):
            lane = self.energy_packets[tp]
            dq = lane.dq

            if tp == PacketType.BALANCED and len(dq):
                assert dq[0].capacity == 0

            for a, b in zip(dq, list(dq)[1:]):
                # canonical ordering + no overlaps (contact OK)
                assert a.precedes(b), f"{a = }, {b = }"
                assert a.start < b.start

        top_blc = self._balanced_top()
        for tp in (PacketType.EXCESS, PacketType.DEFICIT):
            for p in self.energy_packets[tp].dq:
                assert p.starts_at_or_above_level(top_blc), f"{p.start} and {top_blc}"

        assert self.N_unbalanced_total >= 0


    def _tail_capacity_max(self, packet_type: PacketType) -> float:
        lane = self.energy_packets[packet_type]
        tail = lane.peek_right()
        return tail.capacity_max if tail else float("-inf")


    def _balanced_top(self) -> float:
        return self._tail_capacity_max(PacketType.BALANCED)


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


    def lift_head_to(self, packet_type: PacketType, level: float) -> None:
        self.energy_packets[packet_type].lift_front_to(level)

    @phasepair_invariants
    def append_packet_left(self, packet_type: PacketType, energy_packet: EnergyPacket):
        """
        Append a packet of a given type to the left of the appropriate list.
        Asserts that the packet will conserve the canonical order of capacities compared to the BALANCED one and the list of same type.
        """
        # enforce "above balanced top" (if required)
        top_blc = self._balanced_top()

        # canonicalization happens in the lane (absorbs lower-start & overlaps)
        self.energy_packets[packet_type].append_packet_left(energy_packet.lift_to(top_blc))


    @phasepair_invariants
    def append_packet(self, packet_type: PacketType, energy_packet: EnergyPacket ):
        """
        Append a packet of a given type to the appropriate list.
        It will ensure the canonical order of capacities within the list of the same type.
        All packets have to be at least as high as the top of the highest BALANCED packet.
        When a packet has the same or a lower capacity and its capacity has to be increased, it will merge with the topmost packet.
        """

        # enforce "above balanced top"
        top_blc = self._balanced_top()

        # lane enforces: merge touching or lower
        self.energy_packets[packet_type].append_packet(energy_packet.lift_to(top_blc))


    @phasepair_invariants
    def pop_packet_left(self, packet_type: PacketType):
        """
        Will pop the first packet of a given type.
        """
        return self.energy_packets[packet_type].pop_left()

    @phasepair_invariants
    def pop_packet(self, packet_type: PacketType):
        """
        Will pop the last packet of a given type.
        """
        return self.energy_packets[packet_type].pop_right()

    @staticmethod
    def _rec_evt_balance_packets(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if REC_EVTS:
                self.rec_evt(EventType.BALANCED_PHASE)

            res = func(self, *args, **kwargs)

            return res

        return wrapper


    @_rec_evt_balance_packets
    @phasepair_invariants
    def balance_packets(self):
        while self.phase_type == PacketType.UNDEFINED:
            self.balance_first_packet()


    def balance_first_packet(self):
        """
        Take the first packets of the EXCESS and DEFICIT type, determines the residual, adds the BALANCED part and puts the residual back into the appropriate deque.
        """

        pkt_exs = self.energy_packets[PacketType.EXCESS].peek_left()
        pkt_def = self.energy_packets[PacketType.DEFICIT].peek_left()

        if DEBUG_LOG: print(f'[{self.ID}] Balancing EXCESS {pkt_exs} and DEFICIT {pkt_def}')

        # 1. Align Capacities (Lift the lower one to the higher one)
        capacity_bottom = max(pkt_exs.capacity, pkt_def.capacity)
        pkt_exs = self.energy_packets[PacketType.EXCESS].lift_front_to(capacity_bottom).peek_left()
        pkt_def = self.energy_packets[PacketType.DEFICIT].lift_front_to(capacity_bottom).peek_left()

        # 2. Calculate Energy Difference
        # diff > 0: Deficit is larger (Residual is Deficit)
        # diff < 0: Excess is larger (Residual is Excess)
        diff = pkt_def.energy - pkt_exs.energy

        # 4. Create Balanced Packet (using the Deficit packet as container)
        # The balanced amount is the min energy of both.
        pkt_balanced = EnergyPacket(
            capacity=capacity_bottom,
            energy=min(pkt_exs.energy, pkt_def.energy)
        )

        # 3. Handle Residuals
        if diff > -EPS:
            self.energy_packets[PacketType.EXCESS].pop_left()

        if diff < EPS:
            self.energy_packets[PacketType.DEFICIT].pop_left()

        if diff > EPS:
            # Deficit was larger; Excess is fully consumed.
            # We need to put the remaining Deficit back.
            # We can create a new packet or reuse pkt_exs if we wanted,
            # but creating new for residual is cleaner for ownership.
            if DEBUG_LOG:
                print(f'[{self.ID}] DEFICIT remaining')

            if REC_EVTS:
                self.rec_evt(EventType.DEFICIT_REMAINING)

            pkt_def.energy = diff
            self.energy_packets[PacketType.DEFICIT].lift_front_to(pkt_balanced.capacity_max)

        elif diff < -EPS:
            # Excess was larger; Deficit is fully consumed.
            if DEBUG_LOG:
                print(f'[{self.ID}] EXCESS remaining')

            if REC_EVTS:
                self.rec_evt(EventType.EXCESS_REMAINING)

            pkt_exs.energy = -diff
            self.energy_packets[PacketType.EXCESS].lift_front_to(pkt_balanced.capacity_max)


        self.append_packet(PacketType.BALANCED, pkt_balanced)


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

    def rec_evt(self, evt_type: str|EventType):
        EventRecorder().record(Event(evt_type=evt_type, triggered_by=self.ID))

    @property
    def ID(self) -> str:
        s = f'PG {self.index_start}'
        if self.index_start != self.index_end:
            s += f'..{self.index_end}'

        s += f' {self.group_type.name[0:3]}'
        return s


    def balance_group(self, ctx: Context):
        """
        Balancing a group is only required for group_type==UNDEFINED and will only need to check the very first phase pair at index_start.
        """
        if self.group_type == PacketType.BALANCED:
            if DEBUG_LOG:
                print(f'[{self.ID}] Nothing to balance.')

            if REC_EVTS:
                self.rec_evt(EventType.BALANCE_OBSOLETE)

            self.shift_inputs = []
            return

        if self.group_type == PacketType.DEFICIT or self.group_type == PacketType.EXCESS:
            if DEBUG_LOG: print(f'[{self.ID}] A group of type {self.group_type.name} cannot be balanced!')
            raise

        if DEBUG_LOG:
            print(f'[{self.ID}] Balancing group: {self}')

        if REC_EVTS:
            self.rec_evt(EventType.BALANCE_GROUP)

        phase_pair = ctx.phase_pairs[self.index_start]

        phase_pair.balance_packets()

        self.group_type = ctx.phase_pairs[self.index_start].phase_type


        if self.group_type == PacketType.BALANCED:
            self.shift_inputs = [ShiftInput(
                index=None,
                capacity_hurdle=ctx.phase_pairs[self.index_start].energy_packets[PacketType.BALANCED].peek_right().capacity_max
            )]
            if REC_EVTS:
                self.rec_evt(EventType.BALANCE_CREATES_HURDLE)
        else:
            self.shift_inputs = [ShiftInput(
                index=self.index_start,
                capacity_hurdle=0
            )]


        if DEBUG_LOG: print(f'[{self.ID}] Now: {self}')


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


    def can_merge(self, other: 'PhaseGroup') -> bool:
        return PhaseGroup._merge_rules[(self.group_type, other.group_type)][0] is not None


    def merge_with(self, other: 'PhaseGroup'):
        if DEBUG_LOG: print(f'[{self.ID}] Merging with "{other.ID}"')

        new_type, reason = PhaseGroup._merge_rules[(self.group_type, other.group_type)]

        if new_type is None:
            if DEBUG_LOG:
                print(f'[{self.ID}] Merge rejected with reason: {reason}')

            if REC_EVTS:
                evt_mapping = {
                    (PacketType.UNDEFINED, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
                    (PacketType.UNDEFINED, PacketType.BALANCED): EventType.MERGE_REJECTED_UND,
                    (PacketType.UNDEFINED, PacketType.EXCESS): EventType.MERGE_REJECTED_UND,
                    (PacketType.UNDEFINED, PacketType.DEFICIT): EventType.MERGE_REJECTED_UND,
                    (PacketType.BALANCED, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
                    (PacketType.EXCESS, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
                    (PacketType.DEFICIT, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,

                    (PacketType.BALANCED, PacketType.EXCESS): EventType.MERGE_REJECTED_BAL_EXC,
                    (PacketType.DEFICIT, PacketType.BALANCED): EventType.MERGE_REJECTED_DEF_BAL,
                    (PacketType.EXCESS, PacketType.DEFICIT): EventType.MERGE_REJECTED_EXC_DEF,
                    (PacketType.DEFICIT, PacketType.EXCESS): EventType.MERGE_REJECTED_DEF_EXC,
                }

                self.rec_evt(evt_mapping[(self.group_type, other.group_type)])

            return False, reason

        if DEBUG_LOG:
            print(f'[{self.ID}] Merge allowed with reason: {reason}')

        if REC_EVTS:
            evt_mapping = {
                (PacketType.BALANCED, PacketType.BALANCED): EventType.MERGE_BAL_BAL,
                (PacketType.EXCESS, PacketType.EXCESS): EventType.MERGE_EXC_EXC,
                (PacketType.DEFICIT, PacketType.DEFICIT): EventType.MERGE_DEF_DEF,
                (PacketType.BALANCED, PacketType.DEFICIT): EventType.MERGE_BAL_DEF,
                (PacketType.EXCESS, PacketType.BALANCED): EventType.MERGE_EXC_BAL,
            }

            self.rec_evt(evt_mapping[(self.group_type, other.group_type)])

        self.group_type = new_type

        """Merging two groups will allways set the end index of the first one to the end index of the second one."""
        self.index_end = other.index_end

        if self.group_type != PacketType.BALANCED or other.group_type != PacketType.BALANCED:
            self.shift_inputs.extend(other.shift_inputs)
        else: # If both groups are BALANCED, we only keep the higher capacity and do not extend the shift inputs
            if len(other.shift_inputs) == 0:
                pass
            elif len(self.shift_inputs) == 0:
                self.shift_inputs.extend(other.shift_inputs)
            elif self.shift_inputs[-1].capacity_hurdle < other.shift_inputs[-1].capacity_hurdle + EPS:
                self.shift_inputs[-1].capacity_hurdle = other.shift_inputs[-1].capacity_hurdle


        if DEBUG_LOG: print(f'[{self.ID}] Merged successfully. "{other.ID}" can be removed.')
        return True, reason


    def shift(self, ctx: Context):
        """
        For EXCESS groups we iterate over the indices and capacities in reverse direction and shift the to start of the next group.
        """
        assert self.group_type != PacketType.UNDEFINED, f'[{self.ID}] Cannot shift UNDEFINED group!'

        if self.group_type == PacketType.BALANCED or (self.group_type == PacketType.DEFICIT and self.index_start == self.index_end):
            if DEBUG_LOG:
                print(f'[{self.ID}] Nothing to shift.')

            if REC_EVTS:
                self.rec_evt(EventType.SHIFT_GROUP_OBSOLETE)

            if self.group_type == PacketType.DEFICIT:
                self.group_type = PacketType.UNDEFINED
            return

        # shift to the start of the same group for DEFICIT and to the start of the next group for EXCESS
        index_target = self.index_start if self.group_type == PacketType.DEFICIT else (self.index_end + 1) % ctx.N_phases
        phase_pair_target =  ctx.phase_pairs[index_target]

        if DEBUG_LOG:
            print(f'[{self.ID}] Shifting energy packets to {index_target}.')

        if REC_EVTS:
            self.rec_evt(EventType.SHIFT_GROUP)

        capacity_hurdle = 0.0

        # iterate forward for DEFICIT and backward for EXCESS
        shift_inputs = self.shift_inputs if self.group_type == PacketType.DEFICIT else reversed(self.shift_inputs)

        for shift_input in shift_inputs:
            index = shift_input.index

            # hurdle must include BALANCED entries too
            if DEBUG_LOG: print(f'\n[{self.ID}] {shift_input}')

            if capacity_hurdle < shift_input.capacity_hurdle:
                capacity_hurdle = shift_input.capacity_hurdle
                if DEBUG_LOG: print(f'[{self.ID}] Hurdle update to {capacity_hurdle}')


            if index is None or index == index_target:
                """Nothing to shift from a BALANCED index or same index"""
                if DEBUG_LOG: print(f'[{self.ID}] No shift needed.')
                continue

            if DEBUG_LOG: print(f'[{self.ID}] Shift from {index} to {index_target}')


            phase_pair_source = ctx.phase_pairs[index]

            while phase_pair_source.n_packets[self.group_type] > 0:

                if DEBUG_LOG: print(f'\n[{self.ID}] Shift needed for {phase_pair_source.n_packets[self.group_type]} packet(s).')

                pkt = phase_pair_source.pop_packet_left(self.group_type)

                if DEBUG_LOG:
                    print(f'[{self.ID}] Shifting {pkt}')

                if REC_EVTS:
                    evt_mapping = {
                        PacketType.EXCESS: EventType.SHIFT_PACKET_EXCESS,
                        PacketType.DEFICIT: EventType.SHIFT_PACKET_DEFICIT,
                    }
                    self.rec_evt(evt_mapping[self.group_type])

                if pkt.starts_below_level(capacity_hurdle):
                    if DEBUG_LOG:
                        print(f'[{self.ID}] Packet jumped over hurdle {capacity_hurdle} -> increase packets capacity')

                    if REC_EVTS:
                        evt_mapping = {
                            PacketType.EXCESS: EventType.HURDLE_JUMP_BY_EXCESS,
                            PacketType.DEFICIT: EventType.HURDLE_JUMP_BY_DEFICIT,
                        }
                        self.rec_evt(evt_mapping[self.group_type])

                    pkt.lift_to(capacity_hurdle)

                phase_pair_target.append_packet(self.group_type, pkt)

            if DEBUG_LOG: print('')

        self.group_type = PacketType.UNDEFINED if self.group_type == PacketType.DEFICIT else PacketType.BALANCED
        self.shift_inputs = []
        return True



@dataclass
class Context:
    energy_excess_per_phase_initial: List[float]
    energy_deficit_per_phase_initial: List[float]
    N_phases: int = 0

    phase_pairs: List[PhasePair] = None  # The algorithm will store results in this one

    phase_groups: Deque[PhaseGroup] = None  # The algorithm will work on this one

    n_iterations:int = 0

    def rec_evt(self, evt_type: EventType | str):
        EventRecorder().record(Event(evt_type=evt_type, triggered_by='ctx'))

    @property
    def done(self):
        return self.n_unbalanced_excess == 0 or self.n_unbalanced_deficit == 0


    @property
    def N_unbalanced_total(self):
        return sum([phase_pair.N_unbalanced_total for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_excess(self):
        return sum([phase_pair.n_packets_excess for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_deficit(self):
        return sum([phase_pair.n_packets_deficit for phase_pair in self.phase_pairs])


    def __post_init__(self):
        assert len(self.energy_excess_per_phase_initial) == len(self.energy_deficit_per_phase_initial)

        self.N_phases = len(self.energy_deficit_per_phase_initial)

        self.indices_to_balance = deque(range(self.N_phases))

        self.phase_pairs = [PhasePair(
            index_phase=ix,
            energy_excess_initial=energy_excess_initial,
            energy_deficit_initial=energy_deficit_initial,
        ) for ix, (energy_excess_initial, energy_deficit_initial) in enumerate(zip(self.energy_excess_per_phase_initial, self.energy_deficit_per_phase_initial))]

        self.phase_groups = deque([PhaseGroup(
            group_type=PacketType.UNDEFINED,  # A phase-group of type UNDEFINED will need to be balanced first and will then be either EXCESS, DEFICIT, or BALANCED
            index_start=index_phase,
            index_end=index_phase
        ) for index_phase in range(self.N_phases)])


    def balance(self):
        assert not self.done

        if DEBUG_LOG:
            print(f'vvvvvvvvvvvvvvvvv BALANCE vvvvvvvvvvvvvvvvv')
            print(self.format_phase_table_console())

        if REC_EVTS:
            self.rec_evt(EventType.BALANCE_STEP)

        for phase_group in self.phase_groups:
            if DEBUG_LOG: print('\n----')
            phase_group.balance_group(self)

        if DEBUG_LOG:
            print(self.format_phase_table_console())
            print(f'^^^^^^^^^^^^^^^^^^ BALANCE ^^^^^^^^^^^^^^^^^^')


    def rotate_groups_to_anchor(self) -> None:
        for k, g in enumerate(self.phase_groups):
            if g.index_start == 0 or g.index_start > g.index_end:
                if k:
                    self.phase_groups.rotate(-k)
                    if DEBUG_LOG: print(f'Rotating phase groups by {-k}.')
                return


    def merge_groups(self) -> None:
        assert not self.done

        dq = self.phase_groups
        if len(dq) < 2:
            return

        if DEBUG_LOG:
            print("vvvvvvvvvvvvvvvvv MERGE vvvvvvvvvvvvvvvvv")
            print(self.format_phase_table_console())

        if REC_EVTS:
            self.rec_evt(EventType.MERGE_STEP)

        # Canonicalize rotation for determinism
        self.rotate_groups_to_anchor()


        # ---- 1) Linear reduction (treat current deque order as the cycle order)
        stack: list[PhaseGroup] = []
        for g in dq:
            stack.append(g)
            # reduce as long as the last two are mergeable
            while len(stack) >= 2 and stack[-2].can_merge(stack[-1]):
                left = stack[-2]
                right = stack[-1]

                merged, reason = left.merge_with(right)


                if not merged:
                    raise RuntimeError(f"can_merge True but merge_with failed: {reason}")
                stack.pop()  # remove right; left is mutated in place

                if DEBUG_LOG: print(f"Stack (linear): {[pg.ID for pg in stack]}")

        # stack is now reduced for all internal adjacencies (i,i+1)

        # ---- 2) Cyclic wrap-around reduction: repeatedly reduce (last, first)
        # Use deque for O(1) popleft.
        phase_groups_reduced = deque(stack)

        # While boundary pair can merge: merge last -> first (same direction as cyclic adjacency)
        while len(phase_groups_reduced) > 1 and phase_groups_reduced[-1].can_merge(phase_groups_reduced[0]):
            left = phase_groups_reduced[-1]  # last
            right = phase_groups_reduced[0]  # first
            merged, reason = left.merge_with(right)
            if not merged:
                raise RuntimeError(f"can_merge True but merge_with failed: {reason}")
            phase_groups_reduced.popleft()  # remove the consumed 'first'

            if DEBUG_LOG: print(f"Merge (wrap) of boundary groups.")

            # After changing the tail group, it might now merge with its predecessor.
            # Reduce tail locally (like stack reduction, but only near the end).
            while len(phase_groups_reduced) >= 2 and phase_groups_reduced[-2].can_merge(phase_groups_reduced[-1]):
                l2 = phase_groups_reduced[-2]
                r2 = phase_groups_reduced[-1]
                merged2, reason2 = l2.merge_with(r2)
                if not merged2:
                    raise RuntimeError(f"can_merge True but merge_with failed: {reason2}")
                phase_groups_reduced.pop()

                if DEBUG_LOG: print(f"Tail merged again after boundary merge.")

            # Loop condition re-checks the new boundary (new last, new first)

        self.phase_groups = phase_groups_reduced

        # Canonicalize rotation for determinism
        self.rotate_groups_to_anchor()

        if DEBUG_LOG:
            print(self.format_phase_table_console())
            print("^^^^^^^^^^^^^^^^^^ MERGE (stack) ^^^^^^^^^^^^^^^^^^")


    def shift_groups(self):
        assert not self.done
        """Iterate over all phase_groups and shift EXCESS groups to the next DEFICIT group"""
        if DEBUG_LOG:
            print("vvvvvvvvvvvvvvvvv SHIFT vvvvvvvvvvvvvvvvv")
            print(self.format_phase_table_console())

        if REC_EVTS:
            self.rec_evt(EventType.SHIFT_STEP)

        for grp in self.phase_groups:
            if DEBUG_LOG: print('\n----')
            grp.shift(self)

        if DEBUG_LOG:
            print(self.format_phase_table_console())
            print(f'^^^^^^^^^^^^^^^^^^ SHIFT ^^^^^^^^^^^^^^^^^^')


    def run_mEfES(self):
        self.balance()
        self.n_iterations = 0
        while not self.done:
            self.n_iterations += 1
            self.merge_groups()
            self.shift_groups()
            if DEBUG_LOG:
                print(f'\n\n ++++++++++++++++ ITERATION {self.n_iterations} ++++++++++++++ \n\n')

            if REC_EVTS:
                self.rec_evt('NEXT_ITERATION')

            self.balance()
            if DEBUG_LOG: print(f'{self.done = }')


    """ - - - - - - PRETTY PRINT METHODS - - - - - -"""

    def short_phases(self) -> str:
        s = ''
        for pg in self.phase_groups:
            if pg.index_start == 0 or pg.index_start > pg.index_end:
                s += '|'
            s += pg.group_type.name[0]
        return s


    PHASE_COL_TYPES = (PacketType.EXCESS, PacketType.BALANCED, PacketType.DEFICIT)

    @staticmethod
    def _pp_get_pkts(pp: PhasePair, tp: PacketType):
        # Backward-compatible: missing BALANCED -> empty deque
        try:
            return pp.energy_packets[tp].dq
        except KeyError:
            return deque()


    @staticmethod
    def _pp_get_n(pp: PhasePair, tp: PacketType) -> int:
        # Prefer new API
        if hasattr(pp, "n_packets"):
            return int(pp.n_packets[tp])
        # Fallback to old API
        if tp == PacketType.BALANCED:
            return 0
        return int(pp.n_packets.get[tp])


    @staticmethod
    def _fmt_num(x: float) -> str:
        if isinstance(x, int):
            return str(x)
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return f"{x:g}"


    @staticmethod
    def _fmt_packet(pkt: EnergyPacket) -> str:
        return f"{Context._fmt_num(pkt.capacity)},{Context._fmt_num(pkt.energy)}"


    @staticmethod
    def _iter_group_indices(index_start: int, index_end: int, n_phases: int) -> Iterable[int]:
        if index_end is None:
            index_end = index_start
        if index_start <= index_end:
            yield from range(index_start, index_end + 1)
        else:
            yield from range(index_start, n_phases)
            yield from range(0, index_end + 1)


    @staticmethod
    def _group_marker(pg: PhaseGroup) -> str:
        return f'{pg.ID}'[3:]


    def _build_phase_order_and_groups(self) -> tuple[list[int], list[tuple["PhaseGroup", str, list[int]]]]:
        """
        Returns:
          - phase_order: flattened phase indices in current group order (deduped)
          - groups: list of (PhaseGroup, group_marker, indices_in_that_group_after_dedup)
        """
        n = self.N_phases
        seen: set[int] = set()

        phase_order: list[int] = []
        groups: list[tuple[PhaseGroup, str, list[int]]] = []

        for pg in self.phase_groups:
            raw = list(Context._iter_group_indices(pg.index_start, pg.index_end, n))
            kept: list[int] = []
            for i in raw:
                if i in seen:
                    continue
                seen.add(i)
                kept.append(i)
                phase_order.append(i)
            if kept:
                groups.append((pg, Context._group_marker(pg), kept))

        return phase_order, groups


    def format_phase_table_console(self) -> str:
        """
        3 columns per phase: (E, B, D).

        Header merging:
          - group row merged across each group's columns
          - shift-input rows merged per "span rule" (see below)
          - phase-index row merged across the 3 columns of each phase

        Shift-input rows:
          - Row "H"  : capacity_hurdle
          - Row "SI" : shift_input.index
            * if index is not None: aligned to that phase (spans exactly that phase)
            * if index is None    : spans as many phases as possible until the next non-None
                                    index arrives or the end of the PhaseGroup is reached

        Visual boundaries:
          - group boundaries rendered as '||' between groups (all rows)

        Row order: group, H, SI, phase index, phase type, n, ep[...]
        """
        phase_order, groups = self._build_phase_order_and_groups()
        n_types = len(Context.PHASE_COL_TYPES)

        # column specs: (phase_index, packet_type)
        col_specs: list[tuple[int, PacketType]] = []
        for i in phase_order:
            for tp in Context.PHASE_COL_TYPES:
                col_specs.append((i, tp))

        # group boundary positions (between columns)
        boundary_after_col: set[int] = set()
        col_cursor = 0
        for _pg, _marker, idxs in groups:
            span = n_types * len(idxs)
            boundary_after_col.add(col_cursor + span - 1)
            col_cursor += span

        # boundary after phase segments for merged index row (segments are phases)
        boundary_after_phase_seg: set[int] = set()
        phase_cursor = 0
        for _pg, _marker, idxs in groups:
            boundary_after_phase_seg.add(phase_cursor + len(idxs) - 1)
            phase_cursor += len(idxs)

        # per-column rows
        type_map = {PacketType.EXCESS: "e", PacketType.DEFICIT: "d", PacketType.BALANCED: "b"}
        type_row: list[str] = [type_map[tp] for (_i, tp) in col_specs]
        n_row: list[str] = [str(Context._pp_get_n(self.phase_pairs[i], tp)) for (i, tp) in col_specs]

        # packet rows
        max_k = 0
        for i in phase_order:
            pp = self.phase_pairs[i]
            for tp in Context.PHASE_COL_TYPES:
                max_k = max(max_k, len(Context._pp_get_pkts(pp, tp)))

        ep_rows: list[tuple[str, list[str]]] = []
        for k in range(max_k):
            row: list[str] = []
            for i, tp in col_specs:
                pkts = Context._pp_get_pkts(self.phase_pairs[i], tp)
                row.append(Context._fmt_packet(pkts[k]) if k < len(pkts) else "")
            ep_rows.append((f"ep[{k}]", row))

        # widths derived from non-merged rows
        base_rows_for_widths: list[list[str]] = [type_row, n_row] + [r for _, r in ep_rows]
        col_ws = [max((len(r[c]) for r in base_rows_for_widths), default=0) for c in range(len(col_specs))]
        label_w = max(len("n"), *(len(lbl) for lbl, _ in ep_rows), 0)

        def _span_width(c0: int, span_cols: int) -> int:
            # sum(col widths) + 3*(span_cols-1) for internal " | "
            return sum(col_ws[c0:c0 + span_cols]) + 3 * (span_cols - 1)

        def _cell(text: str, width: int) -> str:
            return f"{text:^{width}}"

        def _render_segments(label: str, segments: list[tuple[str, int]],
                             thick_after_seg: set[int] | None = None) -> str:
            thick_after_seg = thick_after_seg or set()
            left = f"{label:<{label_w}}"
            out = [left, " | "]
            for s, (txt, w) in enumerate(segments):
                out.append(_cell(txt, w))
                if s != len(segments) - 1:
                    out.append(" || " if s in thick_after_seg else " | ")
            out.append(" |")
            return "".join(out)

        def _render_unmerged(label: str, cells: list[str]) -> str:
            left = f"{label:<{label_w}}"
            out = [left, " | "]
            for c, cell in enumerate(cells):
                out.append(_cell(cell, col_ws[c]))
                if c != len(cells) - 1:
                    out.append(" || " if c in boundary_after_col else " | ")
            out.append(" |")
            return "".join(out)

        # ---- merged header rows

        # Group row: segments per group
        group_segments: list[tuple[str, int]] = []
        c = 0
        for _pg, marker, idxs in groups:
            span = n_types * len(idxs)
            group_segments.append((marker, _span_width(c, span)))
            c += span
        thick_after_group_seg = set(range(len(group_segments) - 1))

        # Index row: each phase spans n_types columns
        index_segments: list[tuple[str, int]] = []
        c = 0
        for i in phase_order:
            index_segments.append((str(i), _span_width(c, n_types)))
            c += n_types

        # ---- shift-input rows (merged per the rules in the prompt)

        def _build_shift_segments_for_group(
                pg: "PhaseGroup",
                idxs: list[int],
                c0_group: int,
        ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
            """
            Build (H segments, SI segments) for exactly one PhaseGroup.

            SI rule:
              - si.index != None: emit a 1-phase-wide segment aligned to that phase
              - si.index == None: emit one segment spanning from the current cursor up to
                                  (next non-None index) or (group end)
            """
            # map phase index -> position within this group (0..len(idxs)-1)
            pos_map: dict[int, int] = {ix: p for p, ix in enumerate(idxs)}

            sis = list(pg.shift_inputs) if getattr(pg, "shift_inputs", None) else []

            # Precompute "next non-None position" per shift_input (by shift_inputs order)
            next_non_none_pos: list[int | None] = [None] * len(sis)
            nxt: int | None = None
            for j in range(len(sis) - 1, -1, -1):
                next_non_none_pos[j] = nxt
                si = sis[j]
                if si.index is not None and si.index in pos_map:
                    nxt = pos_map[si.index]

            h_segments: list[tuple[str, int]] = []
            si_segments: list[tuple[str, int]] = []

            # phase cursor within idxs
            p = 0

            for j, si in enumerate(sis):
                if si.index is None:
                    end = next_non_none_pos[j] if next_non_none_pos[j] is not None else len(idxs)
                    if end < p:
                        end = p
                    span_phases = end - p
                    if span_phases <= 0:
                        continue

                    w = _span_width(c0_group + p * n_types, span_phases * n_types)
                    h_segments.append((Context._fmt_num(si.capacity_hurdle), w))
                    si_segments.append(("None", w))
                    p = end
                    continue

                # si.index is not None
                if si.index not in pos_map:
                    # index not in printed group (shouldn't happen, but keep printer robust)
                    continue

                pos = pos_map[si.index]

                # fill any uncovered gap before this aligned index with blanks (merged)
                if pos > p:
                    span_phases = pos - p
                    w = _span_width(c0_group + p * n_types, span_phases * n_types)
                    h_segments.append(("", w))
                    si_segments.append(("", w))
                    p = pos

                if pos < p:
                    # already passed this position (out-of-order shift_inputs); skip
                    continue

                # aligned cell exactly 1 phase wide
                w = _span_width(c0_group + p * n_types, n_types)
                h_segments.append((Context._fmt_num(si.capacity_hurdle), w))
                si_segments.append((str(si.index), w))
                p += 1

            # tail fill to group end
            if p < len(idxs):
                span_phases = len(idxs) - p
                w = _span_width(c0_group + p * n_types, span_phases * n_types)
                h_segments.append(("", w))
                si_segments.append(("", w))

            # ensure we always produce at least one segment for the group
            if not h_segments:
                w = _span_width(c0_group, len(idxs) * n_types)
                h_segments = [("", w)]
                si_segments = [("", w)]

            return h_segments, si_segments

        # Build whole-table H and SI segment lists, keeping group boundaries as '||'
        h_segments_all: list[tuple[str, int]] = []
        si_segments_all: list[tuple[str, int]] = []
        thick_after_shift_seg: set[int] = set()

        c0 = 0  # column cursor
        for gi, (pg, _marker, idxs) in enumerate(groups):
            h_segs, si_segs = _build_shift_segments_for_group(pg, idxs, c0)

            h_segments_all.extend(h_segs)
            si_segments_all.extend(si_segs)

            # '||' after the last segment of each group (except final group)
            if gi != len(groups) - 1:
                thick_after_shift_seg.add(len(h_segments_all) - 1)

            c0 += n_types * len(idxs)

        # ---- render
        pg_lines = [
            _render_segments("PG", group_segments, thick_after_seg=thick_after_group_seg),
            _render_segments("H", h_segments_all, thick_after_seg=thick_after_shift_seg),
            _render_segments("SI", si_segments_all, thick_after_seg=thick_after_shift_seg),
        ]
        pp_lines = [
            _render_segments("PP", index_segments, thick_after_seg=boundary_after_phase_seg),
            _render_unmerged("PT", type_row),
        ]

        sep = "-" * len(pg_lines[0])

        out = [
            sep,
            *pg_lines,
            sep,
            *pp_lines,
            sep,
            _render_unmerged("n", n_row),
            sep,
            *[_render_unmerged(lbl, cells) for (lbl, cells) in ep_rows],
            sep,
        ]
        return "\n".join(out)


    def format_phase_table_latex(self) -> str:
        phase_order, groups = self._build_phase_order_and_groups()
        n_types = len(Context.PHASE_COL_TYPES)

        group_cells = []
        for _pg, marker, idxs in groups:
            span = n_types * len(idxs)
            group_cells.append(rf"\multicolumn{{{span}}}{{c}}{{{marker}}}")

        idx_cells = [rf"\multicolumn{{{n_types}}}{{c}}{{{i}}}" for i in phase_order]

        type_map = {PacketType.EXCESS: "e", PacketType.DEFICIT: "d", PacketType.BALANCED: "b"}
        type_cells = []
        for _i in phase_order:
            type_cells.extend([type_map[tp] for tp in Context.PHASE_COL_TYPES])

        n_cells = []
        for i in phase_order:
            pp = self.phase_pairs[i]
            for tp in Context.PHASE_COL_TYPES:
                n_cells.append(str(Context._pp_get_n(pp, tp)))

        max_k = 0
        for i in phase_order:
            pp = self.phase_pairs[i]
            for tp in Context.PHASE_COL_TYPES:
                max_k = max(max_k, len(Context._pp_get_pkts(pp, tp)))

        def latex_row(label: str, cells: list[str]) -> str:
            return " & ".join([label] + cells) + r" \\"

        rows = [
            latex_row("", group_cells),
            latex_row("", idx_cells),
            latex_row("", type_cells),
            latex_row("n", n_cells),
        ]

        for k in range(max_k):
            cells = []
            for i in phase_order:
                pp = self.phase_pairs[i]
                for tp in Context.PHASE_COL_TYPES:
                    pkts = Context._pp_get_pkts(pp, tp)
                    cells.append(Context._fmt_packet(pkts[k]) if k < len(pkts) else "")
            rows.append(latex_row(f"ep[{k}]", cells))

        return "\n".join(rows)


def run_example():
    """
This example is built to exercise the relevant corner-cases for the algorithm’s
**BALANCE -> MERGE -> SHIFT** pipeline on a *cyclic* phase sequence (wrap-around at N−1 -> 0).

-------------------------------------------------------------------------------
Concrete input used in this regression / illustration run
-------------------------------------------------------------------------------

Initial energies per phase (capacity-0 packets):

    energy_excess_per_phase_initial  = [40, 3, 10, 20, 60, 3, 1, 10, 2, 5, 2, 7, 2, 50, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [40, 5, 10, 20, 60, 2, 2, 10, 3, 8, 3, 5, 1, 50, 1, 2, 1, 5]

Each phase index `k` is represented as a **PhasePair** consisting of up to three packet lanes:
- `e` (excess packets)
- `b` (balanced packets)
- `d` (deficit packets)

Initially, each PhasePair contains exactly one excess packet and one deficit packet at capacity 0,
with energies taken from the arrays above.

-------------------------------------------------------------------------------
BALANCE (PhasePair classification + packet splitting)
-------------------------------------------------------------------------------

During **BALANCE**, each PhasePair is converted from type `UND` (undefined) into one of:
- `BAL` (balanced)  if excess == deficit (no split required),
- `EXC` (excess)    if excess > deficit  (split the excess packet at `capacity = deficit`),
- `DEF` (deficit)   if deficit > excess  (split the deficit packet at `capacity = excess`).

After BALANCE, each PhaseGroup stores a `shift_inputs` list. Each element is:

    ShiftInput(index: Optional[int], capacity_hurdle: int)

Interpretation (as printed in the tables):
- Row **SI** prints `shift_input.index` per PhasePair position.
  `None` denotes the PhasePair that anchors the *hurdle update only* (no direct shift).
- Row **H** prints the corresponding `capacity_hurdle`.

In the initial BALANCE of this run, every PhasePair becomes its own PhaseGroup, producing:
    types: "BDBBBEDBDDDEEBEDEE"
(i.e., BAL/DEF/EXC pattern over indices 0..17).

-------------------------------------------------------------------------------
MERGE (non-commutative group algebra, preserving shift direction)
-------------------------------------------------------------------------------

MERGE collapses adjacent PhaseGroups using the directed merge rules. The operation is not
commutative because it must preserve the direction of the later SHIFT.

Allowed merges (as observed in this run):
- Same-type merges:
  - `BAL (+) BAL`, `DEF (+) DEF`, `EXC (+) EXC`
- Direction-preserving merges:
  - `BAL (+) DEF`  (reason: "DEFICIT will be shifted left over BALANCE.")
  - `EXC (+) BAL`  (reason: "EXCESS will be shifted right over BALANCE.")

Not allowed (must be resolved by shifting first or by balancing):
- Any merge involving `UND`
- `BAL (+) EXC` or `DEF (+) BAL` (would lose directional intent)
- `EXC (+) DEF` / `DEF (+) EXC` (direct conflict)

In this run, MERGE demonstrates:
- a cycle-boundary `BAL (+) DEF` merge at indices 0 and 1 -> `0..1 DEF`
- repeated `BAL (+) BAL` merges at 2,3,4 -> `2..4 BAL`
- a long `DEF` chain collapsing to `6..10 DEF`
- adjacent `EXC` merges (`11..12`, `16..17`) and `EXC (+) BAL` absorption at `11..12 (+) 13`
- after later iterations, a wrap-around merge of two `EXC` blocks triggers a *rotation*:
  the log prints `Merged (wrap): Same type` followed by `Rotating phase groups by -2`.

-------------------------------------------------------------------------------
SHIFT (executing ShiftInputs; hurdle updates + conditional capacity lifting)
-------------------------------------------------------------------------------

SHIFT moves packets between PhasePairs inside a merged PhaseGroup, toward a target PhasePair
chosen by the group’s shift direction:

- `DEF` groups shift packets **left** (toward the group’s `index_start`)
- `EXC` groups shift packets **right** (toward the group’s `index_end`)
- `BAL` groups do not shift

SHIFT proceeds by iterating the group’s `ShiftInput` list in order. The log distinguishes:
1) **Hurdle update only** (`ShiftInput(index=None, capacity_hurdle=H)`):
   - Updates the active hurdle to `H`
   - Prints `No shift needed.`
2) **Shift step** (`ShiftInput(index=i, capacity_hurdle=H)`):
   - Prints `Shift from i to target`
   - Removes the top packet from lane `e` or `d` (depending on group type)
   - Attempts to append it at the target.

A key corner-case illustrated by the log:
- If the moved packet’s capacity is below the current hurdle, the log prints:
      `Packet jumped over hurdle X -> increase packets capacity`
  and the packet’s capacity is raised to the hurdle before insertion/merge at the target.

The *append* itself can either:
- append as a new packet (`Packet appended.`), or
- merge energy into an existing top packet at the same lane
  (log lines like `... top at <cap> was higher -> packets energy merged instead`).

This run demonstrates all of the following SHIFT behaviors:
- **Wrap-around shifting** across the cyclic boundary:
  EXC group `16..17` shifts from 17 -> 0 and then 16 -> 0.
- **Hurdle update without shifting** via `index=None` ShiftInputs:
  e.g. `ShiftInput(index=None, capacity_hurdle=40)` inside `0..1 DEF`,
  and `ShiftInput(index=None, capacity_hurdle=50)` inside `11..14 EXC`.
- **Capacity lifting due to hurdle jumps**:
  multiple occurrences of `Packet jumped over hurdle ... -> increase packets capacity`
  (e.g. 3->40, 2->10, 1->50, etc.).
- **Energy merges during append** when the destination already has a higher top capacity.

-------------------------------------------------------------------------------
Convergence and end state (what this log actually ends with)
-------------------------------------------------------------------------------

The log shows **two full iterations** after the initial pass:
- After the first SHIFT, some groups become `UND` again and must be re-balanced.
- Iteration 1 BALANCE produces a reduced set of groups, then MERGE collapses them further,
  including a wrap-around EXC merge that triggers group rotation.
- Iteration 2 BALANCE converts the remaining `UND` group `6..10` into `EXC` with
  `ShiftInput(index=6, capacity_hurdle=51)`, and the run terminates with:
      `self.done = True`

So, this input is a regression/illustration case to ensure:
- table output includes the additional **H** and **SI** rows reflecting `shift_inputs`,
- MERGE exercises both same-type merges and directional merges (`EXC (+) BAL`, `BAL (+) DEF`),
  including a **wrap-around** merge that requires rotating the group order,
- SHIFT demonstrates:
  - hurdle-only updates (`index=None`),
  - capacity lifting when jumping over the hurdle,
  - insertion vs. energy-merge effects at the destination,
  - cyclic boundary behavior.

The end result will be:
- a configuration dominated by BALANCED groups plus one EXCESS group (`6..10 EXC`),
  with the final hurdle recorded as `51` at shift index `6`.

The end result will be:
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            16..5 BAL                                                            ||                                        6..11 EXC                                        ||                       12..15 BAL                       |
H     |                                                                                                                                 ||        0        |                                                                       ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                                       ||                                                        |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     16      |     17      |     18      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8       |      9      |     10      |     11      ||     12      |     13      |      14      |     15      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,4 |   |   | 0,11 |   |   | 0,1 |   |   | 0,20 |   |   | 0,30 |   |   | 0,40 |   |   | 0,3 |   || 71,2 | 0,1  |   |   | 0,50 |   |   | 0,60 |   |   | 0,1 |   |   | 0,5 |   |   | 0,3 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,70 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 3,1  |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 60,2 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 70,1 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    global DEBUG_LOG, CHECK_INVARIANTS
    DEBUG_LOG = True
    CHECK_INVARIANTS = True

    energy_excess_per_phase_initial = [10, 1, 20, 30, 40, 4, 1, 50, 60, 1, 5, 3, 7, 2, 70, 2, 1, 3, 5]
    energy_deficit_per_phase_initial = [10, 2, 20, 30, 40, 3, 2, 50, 60, 2, 6, 4, 5, 1, 70, 1, 2, 1, 4]

    result_ref = """
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            16..5 BAL                                                            ||                                        6..11 EXC                                        ||                       12..15 BAL                       |
H     |                                                                                                                                 ||        0        |                                                                       ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                                       ||                                                        |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     16      |     17      |     18      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8       |      9      |     10      |     11      ||     12      |     13      |      14      |     15      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,4 |   |   | 0,11 |   |   | 0,1 |   |   | 0,20 |   |   | 0,30 |   |   | 0,40 |   |   | 0,3 |   || 71,2 | 0,1  |   |   | 0,50 |   |   | 0,60 |   |   | 0,1 |   |   | 0,5 |   |   | 0,3 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,70 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 3,1  |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 60,2 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 70,1 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    ctx = Context(energy_excess_per_phase_initial=energy_excess_per_phase_initial, energy_deficit_per_phase_initial=energy_deficit_per_phase_initial)
    ctx.run_mEfES()


    result = ctx.format_phase_table_console()
    if ('\n' + result + '\n') == result_ref:
        print('Result matches the reference :-)')
    else:
        print('The result differs from the reference :-(')
        print('Reference:\n', result_ref)

        print('Result:\n', result)



def build_worst_case_cycle(
    n_phases: int,
    *,
    base: int = 100,
    e_low: int = 2,
    e_high: int = 3
) -> Tuple[List[int], List[int]]:
    """
    Deterministic “anti-merge + slow-progress” initializer that enforces the type dynamics:

      Initial (after first BALANCE):  E D B E D B ...  (period 3)
      After SHIFT (only E shifts right): B U B B U B ... (period 3)
      After next BALANCE:               B D B B E B ... (U resolves alternating D/E)
      After MERGE:                      ... collapses to repeating (D,B,E) which is a rotation of (E,D,B),
                                       i.e. again non-mergeable at the group-type level.

    Construction idea (all energies strictly > 0):
      - Pick a large base A=base.
      - For E phases: (excess, deficit) = (A + e_k, A)   => residual excess = e_k
      - For D phases: (excess, deficit) = (A, A + d_k)   => residual deficit = d_k
      - For B phases: (excess, deficit) = (A, A)         => balanced

    After SHIFT, each D-phase receives the residual excess from its left-neighbor E-phase.
    That makes the D-phase UNDEFINED (U) and it will resolve to:
      - D if d_k > e_left
      - E if d_k < e_left

    We enforce an alternating resolution around the ring by choosing:
      for D_k at phase i (i%3==1):
        if k even:  d_k = e_left + 1  (forces D)
        if k odd:   d_k = max(1, e_left - 1) (forces E)

    Constraints:
      - n_phases must be a multiple of 3 to realize a perfect EDB tiling.
      - base, e_low, e_high must be positive integers.

    Returns:
      (energy_excess_per_phase_initial, energy_deficit_per_phase_initial)
    """
    n_phases = int(n_phases / 3) * 3

    if base <= 0 or e_low <= 0 or e_high <= 0:
        raise ValueError("base, e_low, e_high must be positive integers.")

    ex: List[int] = [0] * n_phases
    de: List[int] = [0] * n_phases

    # Choose residuals on E phases in a simple repeating 2-level pattern.
    # You can also just set e_low == e_high to make all E residuals equal.
    e_residuals: List[int] = []
    for k in range(n_phases // 3):
        e_residuals.append(e_low if (k % 2 == 0) else e_high)

    # Fill phases: E at i%3==0, D at i%3==1, B at i%3==2
    d_counter = 0  # counts D phases to alternate their resolution (D, E, D, E, ...)
    for i in range(n_phases):
        r = i % 3

        if r == 0:  # E
            k = i // 3
            e = e_residuals[k]
            ex[i] = base + e
            de[i] = base

        elif r == 1:  # D (will become U after SHIFT due to incoming excess from left E)
            # Left neighbor is the E at i-1 (since pattern is ...E D B...)
            e_left = e_residuals[(i - 1) // 3]

            if d_counter % 2 == 0:
                # Force U -> D after next BALANCE: d > e_left
                d = e_left + 1
            else:
                # Force U -> E after next BALANCE: d < e_left
                d = max(1, e_left - 1)

            ex[i] = base
            de[i] = base + d
            d_counter += 1

        else:  # B
            ex[i] = base
            de[i] = base

    return ex, de







import gc
import math
import time
from dataclasses import dataclass
from typing import Callable, Any, Tuple, List

import numpy as np

def init_random_ctx(n: int, ratio_balanced: float = 0.0) -> "Context":
    import random
    n = int(n)
    n_balanced = int(n * ratio_balanced)
    n_unbalanced = n - n_balanced

    def random_energy() -> float:
        return random.random() * 1000.0

    blc = deque([random_energy() for _ in range(n_balanced)])
    ex  = deque([random_energy() for _ in range(n_unbalanced)])
    de  = deque([random_energy() for _ in range(n_unbalanced)])

    while len(blc):
        insert = random.random() <= ratio_balanced
        ex.rotate(1)
        de.rotate(1)
        if insert:
            e = blc.pop()
            ex.append(e)
            de.append(e)

    # init produces the state for the timed function
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx

def init_neg_corr_ctx(n):
    ex = np.linspace(1.0,1000.0, int(n))
    de = ex[-1::-1]
    # init produces the state for the timed function
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx

def init_worst_case(n) -> Context:
    ex, de = build_worst_case_cycle(int(n), base=100, e_low=30, e_high=40)
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx


def run_ctx(ctx: "Context") -> None:
    # THIS is what is timed (run-only)
    ctx.run_mEfES()


def run_complexity_benchmark():
    @dataclass
    class FitResult:
        a: float
        b: float
        r2: float
        n: np.ndarray
        t: np.ndarray  # run-only median seconds per call

    def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
        ss_res = np.sum((y - yhat) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        return 1.0 - (ss_res / ss_tot if ss_tot > 0 else float("nan"))

    def fit_powerlaw(n: np.ndarray, t: np.ndarray) -> Tuple[float, float, float]:
        mask = t > 0
        if np.count_nonzero(mask) < 2:
            raise RuntimeError("Need at least 2 positive timing samples to fit a power law.")
        x = np.log(n[mask])
        y = np.log(t[mask])
        b, loga = np.polyfit(x, y, deg=1)
        a = float(np.exp(loga))
        yhat = loga + b * x
        return a, float(b), float(_r2(y, yhat))

    def complexity_benchmark_run_only(
            init_fn: Callable[[int], Any],
            run_fn: Callable[[Any], None],
            n_min: int = 10 ** 2,
            n_max: int = 10 ** 5,
            n_points: int = 12,
            repeats: int = 9,
            min_total_run_time: float = 0.25,
            warmup: int = 1,
            disable_gc: bool = True,
            progress: bool = True,
            print_every: int = 1,
    ) -> FitResult:
        """
        Benchmarks RUN TIME ONLY for run_fn(state), while still calling init_fn(n) once per execution.
        Prints running fit after each n (once >=2 timing points exist), if progress=True.
        """
        if n_min <= 0 or n_max <= 0 or n_min >= n_max:
            raise ValueError("Require 0 < n_min < n_max.")
        if n_points < 2:
            raise ValueError("n_points must be >= 2.")
        if repeats < 3:
            raise ValueError("Use repeats>=3 for a stable median.")

        n_vals = np.unique(np.round(np.logspace(math.log10(n_min), math.log10(n_max), n_points)).astype(int))
        t_vals: List[float] = []

        def run_only_loops(n: int, loops: int) -> float:
            """Total RUN time over `loops` executions (init called each time, not timed)."""
            if disable_gc:
                gc_was_enabled = gc.isenabled()
                gc.disable()
            try:
                total = 0.0
                for _ in range(loops):
                    state = init_fn(n)  # NOT timed
                    t0 = time.perf_counter()
                    run_fn(state)  # timed
                    total += (time.perf_counter() - t0)
                return total
            finally:
                if disable_gc and gc_was_enabled:
                    gc.enable()

        # Warmup (not recorded)
        for _ in range(max(0, warmup)):
            s = init_fn(int(n_vals[0]))
            run_fn(s)

        for i, n in enumerate(n_vals):
            # probe one-call run time (init excluded from probe timing too)
            probe = [run_only_loops(int(n), loops=1) for _ in range(3)]
            one_call = float(np.median(probe))
            loops = 10_000 if one_call <= 0.0 else max(1, int(math.ceil(min_total_run_time / one_call)))

            per_call_samples = []
            for _ in range(repeats):
                total_run = run_only_loops(int(n), loops=loops)
                per_call_samples.append(total_run / loops)

            t_med = float(np.median(per_call_samples))
            t_vals.append(t_med)

            # Running fit + print
            if progress and ((i + 1) % print_every == 0):
                n_arr = np.array(n_vals[: i + 1], dtype=float)
                t_arr = np.array(t_vals, dtype=float)

                if len(t_arr) >= 2 and np.all(t_arr > 0):
                    a, b, r2 = fit_powerlaw(n_arr, t_arr)
                    print(
                        f"FitResults for n in range {int(n_arr[0])} to {int(n_arr[-1])} "
                        f"({len(n_arr)} pts): a={a:.6e}, b={b:.6f}, R²={r2:.6f} | "
                        f"last: n={int(n)}, t={t_med:.6e}s"
                    )
                else:
                    print(
                        f"Collected {len(t_arr)} point(s) so far; need >=2 for fit. "
                        f"last: n={int(n)}, t={t_med:.6e}s"
                    )

        n_arr = np.array(n_vals, dtype=float)
        t_arr = np.array(t_vals, dtype=float)
        a, b, r2 = fit_powerlaw(n_arr, t_arr)
        return FitResult(a=a, b=b, r2=r2, n=n_arr, t=t_arr)

    res = complexity_benchmark_run_only(
        init_fn=lambda n: init_random_ctx(n, ratio_balanced=0.0),
        # init_fn=lambda n: init_neg_corr_ctx(n),
        run_fn=run_ctx,
        n_min=10 ** 2,
        n_max=10 ** 7,
        n_points=12,
        repeats=5,
        min_total_run_time=0.0001,
        warmup=2,
        disable_gc=True,
    )

    print("Fit: t(n) ≈ a * n^b   (RUN-ONLY; init excluded)")
    print(f"a  = {res.a:.6e}")
    print(f"b  = {res.b:.6f}")
    print(f"R² = {res.r2:.6f}")
    print("\nSamples (median seconds per call, run-only):")
    for n, t in zip(res.n.astype(int), res.t):
        print(f"n={n:>7d}  t={t:.6e}")


def run_worst_case(n):
    ctx = init_worst_case(n)
    ctx.run_mEfES()



if __name__ == "__main__":

    #run_example()
    #run_worst_case(n=1000)

    run_complexity_benchmark()

