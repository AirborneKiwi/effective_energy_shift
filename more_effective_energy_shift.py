from __future__ import annotations
from functools import wraps

from enum import IntEnum, Enum, auto
from collections import deque, defaultdict
from dataclasses import dataclass, field, InitVar
from os import times_result

from typing import Deque, List, Set, Dict, Tuple, Iterable
from typing import Callable, TypeVar, ParamSpec, cast


class PacketType(IntEnum):
    EXCESS = 0
    DEFICIT = 1
    BALANCED = 2
    UNDEFINED = 3


@dataclass
class EnergyPacket:
    capacity: float
    energy: float

    @property
    def capacity_max(self) -> float:
        return self.capacity + self.energy

EPS = 1e-12

P = ParamSpec("P")
R = TypeVar("R")

# Toggle at import-time / runtime.
CHECK_INVARIANTS = True
DEBUG_LOG = True


class EventType(Enum):

    NEXT_ITERATION = auto(),

    BALANCE_STEP = auto(),

    BALANCE_OBSOLETE = auto(),
    BALANCING_GROUP = auto(),

    EXCESS_BELOW_DEFICIT = auto(),
    DEFICIT_BELOW_EXCESS = auto(),

    EXCESS_REMAINING = auto(),
    DEFICIT_REMAINING = auto(),
    BALANCED_PHASE = auto(),

    BALANCED_ABSORBED_AT_TOP = auto(),
    BALANCED_ABSORBED_AT_BOTTOM = auto(),
    BALANCED_HOVERS_AT_TOP = auto(),
    BALANCED_HOVERS_AT_BOTTOM = auto(),

    EXCESS_ABSORBED_AT_TOP = auto(),
    EXCESS_ABSORBED_AT_BOTTOM = auto(),
    EXCESS_HOVERS_AT_TOP = auto(),
    EXCESS_HOVERS_AT_BOTTOM = auto(),

    DEFICIT_ABSORBED_AT_TOP = auto(),
    DEFICIT_ABSORBED_AT_BOTTOM = auto(),
    DEFICIT_HOVERS_AT_TOP = auto(),
    DEFICIT_HOVERS_AT_BOTTOM = auto(),

    EXCESS_RAISED_TO_BALANCED_TOP = auto(),
    DEFICIT_RAISED_TO_BALANCED_TOP = auto(),
    BALANCED_RAISED_TO_BALANCED_TOP = auto(),

    BALANCE_CREATES_HURDLE = auto(),

    SHIFT_STEP = auto(),

    SHIFTING_GROUP = auto(),
    SHIFT_OBSOLETE = auto(),
    SHIFT_EXCESS_PACKET = auto(),
    SHIFT_DEFICIT_PACKET = auto(),
    EXCESS_JUMPS_HURDLE = auto(),
    DEFICIT_JUMPS_HURDLE = auto(),

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
        self.observed_events: Dict[EventType, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.n_observed_events: int = 0


    def record(self, event: Event):
        if isinstance(event.evt_type, EventType):
            event.evt_type = event.evt_type.name

        if event.evt_type not in self.observed_events:
            self.observed_events[event.evt_type] = []

        event.id = self.n_observed_events
        self.observed_events[event.evt_type].append(event)
        self.n_observed_events += 1


    def __str__(self):
        s = ''
        for event_type, events in self.observed_events.items():
            s += f'{event_type}: {len(events)}\n'
        return s


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

    energy_packets: Dict[PacketType, Deque[EnergyPacket]] = field(default_factory=lambda: {tp: deque() for tp in [PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED]})
    n_packets: Dict[PacketType, int] = field(default_factory = lambda: {tp: 0 for tp in [PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED]})

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


    def _check_invariants(self):
        for tp in (PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED):
            assert self.n_packets[tp] == len(self.energy_packets[tp])
            dq = self.energy_packets[tp]
            for a, b in zip(dq, list(dq)[1:]):
                assert a.capacity_max <= b.capacity + EPS

        top_blc = self._balanced_top()
        for tp in (PacketType.EXCESS, PacketType.DEFICIT):
            for p in self.energy_packets[tp]:
                assert p.capacity + EPS >= top_blc

        assert self.N_unbalanced_total >= 0


    def _tail_capacity_max(self, packet_type: PacketType) -> float:
        dq = self.energy_packets[packet_type]
        return dq[-1].capacity_max if dq else float("-inf")


    def _balanced_top(self) -> float:
        return self._tail_capacity_max(PacketType.BALANCED)


    @property
    def phase_type(self):
        if self.n_packets[PacketType.EXCESS] == 0 and self.n_packets[PacketType.DEFICIT] == 0:
            return PacketType.BALANCED

        if self.n_packets[PacketType.EXCESS] >= 1 and self.n_packets[PacketType.DEFICIT] >= 1:
            return PacketType.UNDEFINED

        if self.n_packets[PacketType.EXCESS] >= 1:
            return PacketType.EXCESS

        if self.n_packets[PacketType.DEFICIT] >= 1:
            return PacketType.DEFICIT

        raise


    @property
    def N_unbalanced_total(self) -> int:
        return self.n_packets[PacketType.EXCESS] + self.n_packets[PacketType.DEFICIT]


    def _absorb_front_overlaps(self, packet_type: PacketType, pkt: EnergyPacket) -> EnergyPacket:
        """
        Merge packets from the *front* of deque `packet_type` into `pkt` while pkt reaches/touches them.
        Potentially absorbs multiple packets.
        """
        dq = self.energy_packets[packet_type]

        while dq and pkt.capacity_max >= dq[0].capacity - EPS:
            nxt = dq.popleft()
            self.n_packets[packet_type] -= 1
            pkt.energy += nxt.energy

            if DEBUG_LOG:
                print(f'[{self.ID}] Packet {pkt} absorbed {nxt}. New packet count is {self.n_packets[packet_type]}')
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_ABSORBED_AT_BOTTOM,
                    PacketType.DEFICIT: EventType.DEFICIT_ABSORBED_AT_BOTTOM,
                    PacketType.BALANCED: EventType.BALANCED_ABSORBED_AT_BOTTOM,
                }
                self.rec_evt(evt_type_mapping[packet_type])

        return pkt


    def _lift_unbalanced_heads_to_balanced_top(self) -> None:
        """
        After BALANCED grows, EXCESS/DEFICIT heads might now be below the new top_blc.
        Lift the head to top_blc and merge forward if that causes overlaps.
        Only the head needs checking because deques are ordered.
        """
        top_blc = self._balanced_top()
        for packet_type in (PacketType.EXCESS, PacketType.DEFICIT):
            dq = self.energy_packets[packet_type]
            if not dq:
                continue
            if dq[0].capacity + EPS >= top_blc:
                continue

            # take head out, lift it, then absorb any now-reachable packets
            head = dq.popleft()
            self.n_packets[packet_type] -= 1
            head.capacity = top_blc
            if DEBUG_LOG:
                print(f'[{self.ID}] {packet_type.name} head detached and raised above BALANCED top which might cause absorption. New packet count is {self.n_packets[packet_type]}')
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_RAISED_TO_BALANCED_TOP,
                    PacketType.DEFICIT: EventType.DEFICIT_RAISED_TO_BALANCED_TOP,
                    PacketType.BALANCED: EventType.BALANCED_RAISED_TO_BALANCED_TOP,
                }

                self.rec_evt(evt_type_mapping[packet_type])

            head = self._absorb_front_overlaps(packet_type, head)

            dq.appendleft(head)
            self.n_packets[packet_type] += 1
            if DEBUG_LOG:
                print(f'[{self.ID}] {packet_type.name} head reattached. New packet count is {self.n_packets[packet_type]}')


    @phasepair_invariants
    def append_packet_left(self, packet_type: PacketType, energy_packet: EnergyPacket):
        """
        Append a packet of a given type to the left of the appropriate list.
        Asserts that the packet will conserve the canonical order of capacities compared to the BALANCED one and the list of same type.
        """
        if DEBUG_LOG: print(f'[{self.ID}] Appending {packet_type.name} packet left: {energy_packet}')

        top_blc = self._balanced_top()

        # enforce/repair "above balanced"
        if energy_packet.capacity < top_blc - EPS:
            if DEBUG_LOG:
                print(f'[{self.ID}] Balanced top at {top_blc} was higher -> increased the packets capacity')
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_RAISED_TO_BALANCED_TOP,
                    PacketType.DEFICIT: EventType.DEFICIT_RAISED_TO_BALANCED_TOP,
                    PacketType.BALANCED: EventType.BALANCED_RAISED_TO_BALANCED_TOP,
                }

                self.rec_evt(evt_type_mapping[packet_type])

            energy_packet.capacity = top_blc


        dq = self.energy_packets[packet_type]
        if dq and energy_packet.capacity > dq[0].capacity + EPS:
            # not actually a "left append" case; fall back to tail insertion
            if DEBUG_LOG:
                print(f'[{self.ID}] {packet_type.name} Appending left is not allowed! Fallback to normal append.')
                self.rec_evt(f'WRONG APPEND CALL!')

            return self.append_packet(packet_type, energy_packet)

        energy_packet = self._absorb_front_overlaps(packet_type, energy_packet)
        dq.appendleft(energy_packet)
        self.n_packets[packet_type] += 1

        if DEBUG_LOG:
            print(f'[{self.ID}] Packet appended left. New packet count is {self.n_packets[packet_type]}')
            self.rec_evt(f'{packet_type.name} PACKET APPEND AT BOTTOM')


    @phasepair_invariants
    def append_packet(self, packet_type: PacketType, energy_packet: EnergyPacket ):
        """
        Append a packet of a given type to the appropriate list.
        It will ensure the canonical order of capacities within the list of the same type.
        All packets have to be at least as high as the top of the highest BALANCED packet.
        When a packet has the same or a lower capacity and its capacity has to be increased, it will merge with the topmost packet.
        """
        if DEBUG_LOG: print(f'[{self.ID}] Appending {packet_type.name} packet: {energy_packet}')

        top_blc = self._balanced_top()

        if energy_packet.capacity < top_blc - EPS:
            energy_packet.capacity = top_blc
            if DEBUG_LOG:
                print(f'[{self.ID}] Balanced top at {top_blc} was higher -> increased the packets capacity')
                evt_type_mapping = {
                    PacketType.EXCESS: EventType.EXCESS_RAISED_TO_BALANCED_TOP,
                    PacketType.DEFICIT: EventType.DEFICIT_RAISED_TO_BALANCED_TOP,
                    PacketType.BALANCED: EventType.BALANCED_RAISED_TO_BALANCED_TOP,
                }

                self.rec_evt(evt_type_mapping[packet_type])

        dq = self.energy_packets[packet_type]
        if dq:
            last = dq[-1]
            if energy_packet.capacity <= last.capacity_max + EPS:
                # merge contiguously/overlapping into last
                if DEBUG_LOG:
                    print(f'[{self.ID}] {packet_type.name} top at {last.capacity_max} was higher -> packets energy merged instead')
                    evt_type_mapping = {
                        PacketType.EXCESS: EventType.EXCESS_ABSORBED_AT_TOP,
                        PacketType.DEFICIT: EventType.DEFICIT_ABSORBED_AT_TOP,
                        PacketType.BALANCED: EventType.BALANCED_ABSORBED_AT_TOP,
                    }

                    self.rec_evt(evt_type_mapping[packet_type])


                energy_packet.capacity = last.capacity_max
                last.energy += energy_packet.energy

                # IMPORTANT: if we extended BALANCED, lift heads before invariants run
                if packet_type == PacketType.BALANCED:
                    self._lift_unbalanced_heads_to_balanced_top()
                return

        dq.append(energy_packet)
        self.n_packets[packet_type] += 1

        if DEBUG_LOG:
            print(f'[{self.ID}] Packet appended. New packet count is {self.n_packets[packet_type]}')
            evt_type_mapping = {
                PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_TOP,
                PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_TOP,
                PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_TOP,
            }

            self.rec_evt(evt_type_mapping[packet_type])

        if packet_type == PacketType.BALANCED:
            self._lift_unbalanced_heads_to_balanced_top()


    @phasepair_invariants
    def pop_packet_left(self, packet_type: PacketType):
        """
        Will pop the first packet of a given type.
        """
        pkt = self.energy_packets[packet_type].popleft()
        self.n_packets[packet_type] -= 1  # increase the number of packets

        if DEBUG_LOG: print(f'[{self.ID}] First {packet_type.name} packet removed. New packet count is {self.n_packets[packet_type]}')
        return pkt


    @phasepair_invariants
    def pop_packet(self, packet_type: PacketType):
        """
        Will pop the last packet of a given type.
        """
        pkt = self.energy_packets[packet_type].pop()
        self.n_packets[packet_type] -= 1  # increase the number of packets
        if DEBUG_LOG: print(f'[{self.ID}] Last {packet_type.name} packet removed. New packet count is {self.n_packets[packet_type]}')
        return pkt


    @phasepair_invariants
    def balance_packets(self):
        self.rec_evt(EventType.BALANCED_PHASE)
        while self.phase_type == PacketType.UNDEFINED:
            self.balance_first_packet()
            if DEBUG_LOG: print('')


    def balance_first_packet(self):
        """
        Take the first packets of the EXCESS and DEFICIT type, determines the residual, adds the BALANCED part and puts the residual back into the appropriate deque.
        """

        pkt_exs = self.pop_packet_left(PacketType.EXCESS)
        pkt_def = self.pop_packet_left(PacketType.DEFICIT)
        if DEBUG_LOG: print(f'[{self.ID}] Balancing EXCESS {pkt_exs} and DEFICIT {pkt_def}')

        # 1. Align Capacities (Lift the lower one to the higher one)
        # Note: We rely on _absorb_front_overlaps to handle the consequences of lifting
        if pkt_exs.capacity < pkt_def.capacity:
            if DEBUG_LOG:
                print(f'[{self.ID}] EXCESS below DEFICIT -> increased the EXCESS packets capacity')
                self.rec_evt(EventType.EXCESS_BELOW_DEFICIT)

            pkt_exs.capacity = pkt_def.capacity
            pkt_exs = self._absorb_front_overlaps(PacketType.EXCESS, pkt_exs)
        elif pkt_def.capacity < pkt_exs.capacity:
            if DEBUG_LOG:
                print(f'[{self.ID}] DEFICIT below EXCESS -> increased the DEFICIT packets capacity')
                self.rec_evt(EventType.DEFICIT_BELOW_EXCESS)

            pkt_def.capacity = pkt_exs.capacity
            pkt_def = self._absorb_front_overlaps(PacketType.DEFICIT, pkt_def)

        # 2. Calculate Energy Difference
        # diff > 0: Deficit is larger (Residual is Deficit)
        # diff < 0: Excess is larger (Residual is Excess)
        diff = pkt_def.energy - pkt_exs.energy

        # 3. Create Balanced Packet (using the Deficit packet as container)
        # The balanced amount is the min energy of both.
        balanced_energy = min(pkt_exs.energy, pkt_def.energy)

        # We can reuse pkt_def for the balanced result to save an allocation
        pkt_balanced = pkt_def
        pkt_balanced.energy = balanced_energy
        # capacity is already aligned from Step 1

        # 4. Handle Residuals
        if diff > EPS:
            # Deficit was larger; Excess is fully consumed.
            # We need to put the remaining Deficit back.
            # We can create a new packet or reuse pkt_exs if we wanted,
            # but creating new for residual is cleaner for ownership.
            if DEBUG_LOG:
                print(f'[{self.ID}] DEFICIT remaining')
                self.rec_evt(EventType.DEFICIT_REMAINING)

            pkt_residual = EnergyPacket(capacity=pkt_balanced.capacity_max, energy=diff)
            self.append_packet_left(PacketType.DEFICIT, pkt_residual)

        elif diff < -EPS:
            # Excess was larger; Deficit is fully consumed.
            if DEBUG_LOG:
                print(f'[{self.ID}] EXCESS remaining')
                self.rec_evt(EventType.EXCESS_REMAINING)

            pkt_residual = EnergyPacket(capacity=pkt_balanced.capacity_max, energy=-diff)
            self.append_packet_left(PacketType.EXCESS, pkt_residual)

        # 5. Store Balanced
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
                self.rec_evt(EventType.BALANCE_OBSOLETE)
            self.shift_inputs = []
            return

        if self.group_type == PacketType.DEFICIT or self.group_type == PacketType.EXCESS:
            if DEBUG_LOG: print(f'[{self.ID}] A group of type {self.group_type.name} cannot be balanced!')
            raise

        if DEBUG_LOG:
            print(f'[{self.ID}] Balancing group: {self}')
            self.rec_evt(EventType.BALANCING_GROUP)

        phase_pair = ctx.phase_pairs[self.index_start]

        phase_pair.balance_packets()

        self.group_type = ctx.phase_pairs[self.index_start].phase_type


        if self.group_type == PacketType.BALANCED:
            self.shift_inputs = [ShiftInput(
                index=None,
                capacity_hurdle=ctx.phase_pairs[self.index_start].energy_packets[PacketType.BALANCED][-1].capacity_max
            )]
            if DEBUG_LOG:
                self.rec_evt(EventType.BALANCE_CREATES_HURDLE)
        else:
            self.shift_inputs = [ShiftInput(
                index=self.index_start,
                capacity_hurdle=ctx.phase_pairs[self.index_start].energy_packets[self.group_type][0].capacity
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
                self.rec_evt(EventType.SHIFT_OBSOLETE)

            if self.group_type == PacketType.DEFICIT:
                self.group_type = PacketType.UNDEFINED
            return

        # shift to the start of the same group for DEFICIT and to the start of the next group for EXCESS
        index_target = self.index_start if self.group_type == PacketType.DEFICIT else (self.index_end + 1) % ctx.N_phases
        phase_pair_target =  ctx.phase_pairs[index_target]

        if DEBUG_LOG:
            print(f'[{self.ID}] Shifting energy packets to {index_target}.')
            self.rec_evt(EventType.SHIFTING_GROUP)

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
                    evt_mapping = {
                        PacketType.EXCESS: EventType.SHIFT_EXCESS_PACKET,
                        PacketType.DEFICIT: EventType.SHIFT_DEFICIT_PACKET,
                    }
                    self.rec_evt(evt_mapping[self.group_type])

                if pkt.capacity < capacity_hurdle - EPS:
                    if DEBUG_LOG:
                        print(f'[{self.ID}] Packet jumped over hurdle {capacity_hurdle} -> increase packets capacity')
                        evt_mapping = {
                            PacketType.EXCESS: EventType.EXCESS_JUMPS_HURDLE,
                            PacketType.DEFICIT: EventType.DEFICIT_JUMPS_HURDLE,
                        }
                        self.rec_evt(evt_mapping[self.group_type])

                    pkt.capacity = capacity_hurdle

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
        return sum([phase_pair.n_packets[PacketType.EXCESS] for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_deficit(self):
        return sum([phase_pair.n_packets[PacketType.DEFICIT] for phase_pair in self.phase_pairs])


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
            return pp.energy_packets[tp]
        except KeyError:
            return deque()


    @staticmethod
    def _pp_get_n(pp: PhasePair, tp: PacketType) -> int:
        # Prefer new API
        if hasattr(pp, "n_packets"):
            return int(pp.n_packets.get(tp, 0))
        # Fallback to old API
        if tp == PacketType.BALANCED:
            return 0
        return int(pp.n_packets.get(tp, 0))


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
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            15..5 BAL                                                            ||                                6..10 EXC                                 ||                       11..14 BAL                       |
H     |                                                                                                                                 ||       51        |                                                        ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                        ||                                                        |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     15      |     16      |     17      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8      |      9      |     10      ||     11      |     12      |      13      |     14      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,5 |   |   | 0,42 |   |   | 0,3 |   |   | 0,10 |   |   | 0,20 |   |   | 0,60 |   |   | 0,2 |   || 51,2 | 0,1  |   |   | 0,10 |   |   | 0,2 |   |   | 0,5 |   |   | 0,2 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,50 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 2,1  |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 42,4 |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 50,1 |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    global DEBUG_LOG, CHECK_INVARIANTS
    DEBUG_LOG = True
    CHECK_INVARIANTS = True

    energy_excess_per_phase_initial = [10, 1, 20, 30, 40, 4, 1, 50, 60, 1, 5, 3, 7, 2, 70, 2, 1, 3, 5]
    energy_deficit_per_phase_initial = [10, 2, 20, 30, 40, 3, 2, 50, 60, 2, 6, 4, 5, 1, 70, 1, 2, 1, 4]

    result_ref = """
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            15..5 BAL                                                            ||                                6..10 EXC                                 ||                       11..14 BAL                       |
H     |                                                                                                                                 ||       51        |                                                        ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                        ||                                                        |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     15      |     16      |     17      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8      |      9      |     10      ||     11      |     12      |      13      |     14      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,5 |   |   | 0,42 |   |   | 0,3 |   |   | 0,10 |   |   | 0,20 |   |   | 0,60 |   |   | 0,2 |   || 51,2 | 0,1  |   |   | 0,10 |   |   | 0,2 |   |   | 0,5 |   |   | 0,2 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,50 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 2,1  |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 42,4 |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 50,1 |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
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



if __name__ == '__main__':


    n = 100
    ex, de = build_worst_case_cycle(n, base=100, e_low=30, e_high=40)
    
    ctx = Context(energy_excess_per_phase_initial=ex,
                  energy_deficit_per_phase_initial=de)
    ctx.run_mEfES()


    #run_example()

    print(EventRecorder())
