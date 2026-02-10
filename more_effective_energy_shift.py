from __future__ import annotations
from functools import wraps

from enum import IntEnum
from collections import deque
from dataclasses import dataclass, field, InitVar

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
    energy_packets: Dict[PacketType, Deque[EnergyPacket]] = field(default_factory=lambda: {tp: deque() for tp in [PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED]})
    n_packets: Dict[PacketType, int] = field(default_factory = lambda: {tp: 0 for tp in [PacketType.EXCESS, PacketType.DEFICIT, PacketType.BALANCED]})

    energy_excess_initial: InitVar[float | None] = None
    energy_deficit_initial: InitVar[float | None] = None


    def __post_init__(self, energy_excess_initial: float, energy_deficit_initial: float):
        self.append_packet(
            packet_type=PacketType.EXCESS,
            energy_packet=EnergyPacket(capacity=0, energy=energy_excess_initial)
        )
        self.append_packet(
            packet_type=PacketType.DEFICIT,
            energy_packet=EnergyPacket(capacity=0, energy=energy_deficit_initial)
        )


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


    def _tail_capacity_max(self, tp: PacketType) -> float:
        dq = self.energy_packets[tp]
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


    def _absorb_front_overlaps(self, tp: PacketType, pkt: EnergyPacket) -> EnergyPacket:
        """
        Merge packets from the *front* of deque `tp` into `pkt` while pkt reaches/touches them.
        Potentially absorbs multiple packets.
        """
        dq = self.energy_packets[tp]

        while dq and pkt.capacity_max >= dq[0].capacity - EPS:
            nxt = dq.popleft()
            self.n_packets[tp] -= 1
            pkt.energy += nxt.energy

        return pkt


    def _lift_unbalanced_heads_to_balanced_top(self) -> None:
        """
        After BALANCED grows, EXCESS/DEFICIT heads might now be below the new top_blc.
        Lift the head to top_blc and merge forward if that causes overlaps.
        Only the head needs checking because deques are ordered.
        """
        top_blc = self._balanced_top()
        for tp in (PacketType.EXCESS, PacketType.DEFICIT):
            dq = self.energy_packets[tp]
            if not dq:
                continue
            if dq[0].capacity + EPS >= top_blc:
                continue

            # take head out, lift it, then absorb any now-reachable packets
            head = dq.popleft()
            self.n_packets[tp] -= 1
            head.capacity = top_blc
            head = self._absorb_front_overlaps(tp, head)

            dq.appendleft(head)
            self.n_packets[tp] += 1


    @phasepair_invariants
    def append_packet_left(self, packet_type: PacketType, energy_packet: EnergyPacket):
        """
        Append a packet of a given type to the left of the appropriate list.
        Asserts that the packet will conserve the canonical order of capacities compared to the BALANCED one and the list of same type.
        """
        top_blc = self._balanced_top()

        # enforce/repair "above balanced"
        if energy_packet.capacity < top_blc - EPS:
            energy_packet.capacity = top_blc

        dq = self.energy_packets[packet_type]
        if dq and energy_packet.capacity > dq[0].capacity + EPS:
            # not actually a "left append" case; fall back to tail insertion
            return self.append_packet(packet_type, energy_packet)

        energy_packet = self._absorb_front_overlaps(packet_type, energy_packet)
        dq.appendleft(energy_packet)
        self.n_packets[packet_type] += 1


    @phasepair_invariants
    def append_packet(self, packet_type: PacketType, energy_packet: EnergyPacket ):
        """
        Append a packet of a given type to the appropriate list.
        It will ensure the canonical order of capacities within the list of the same type.
        All packets have to be at least as high as the top of the highest BALANCED packet.
        When a packet has the same or a lower capacity and its capacity has to be increased, it will merge with the topmost packet.
        """
        top_blc = self._balanced_top()

        if energy_packet.capacity < top_blc - EPS:
            energy_packet.capacity = top_blc

        dq = self.energy_packets[packet_type]
        if dq:
            last = dq[-1]
            if energy_packet.capacity <= last.capacity_max + EPS:
                # merge contiguously/overlapping into last
                energy_packet.capacity = last.capacity_max
                last.energy += energy_packet.energy

                # IMPORTANT: if we extended BALANCED, lift heads before invariants run
                if packet_type == PacketType.BALANCED:
                    self._lift_unbalanced_heads_to_balanced_top()
                return

        dq.append(energy_packet)
        self.n_packets[packet_type] += 1

        if packet_type == PacketType.BALANCED:
            self._lift_unbalanced_heads_to_balanced_top()


    @phasepair_invariants
    def pop_packet_left(self, packet_type: PacketType):
        """
        Will pop the first packet of a given type.
        """
        pkt = self.energy_packets[packet_type].popleft()
        self.n_packets[packet_type] -= 1  # increase the number of packets
        return pkt


    @phasepair_invariants
    def pop_packet(self, packet_type: PacketType):
        """
        Will pop the last packet of a given type.
        """
        pkt = self.energy_packets[packet_type].pop()
        self.n_packets[packet_type] -= 1  # increase the number of packets

        return pkt


    @phasepair_invariants
    def balance_packet(self):
        """
        Take the first packets of the EXCESS and DEFICIT type, determines the residual, adds the BALANCED part and puts the residual back into the appropriate deque.
        """

        pkt_exs = self.pop_packet_left(PacketType.EXCESS)
        pkt_def = self.pop_packet_left(PacketType.DEFICIT)

        # 1. Align Capacities (Lift the lower one to the higher one)
        # Note: We rely on _absorb_front_overlaps to handle the consequences of lifting
        if pkt_exs.capacity < pkt_def.capacity:
            pkt_exs.capacity = pkt_def.capacity
            pkt_exs = self._absorb_front_overlaps(PacketType.EXCESS, pkt_exs)
        elif pkt_def.capacity < pkt_exs.capacity:
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
            pkt_residual = EnergyPacket(capacity=pkt_balanced.capacity_max, energy=diff)
            self.append_packet_left(PacketType.DEFICIT, pkt_residual)

        elif diff < -EPS:
            # Excess was larger; Deficit is fully consumed.
            pkt_residual = EnergyPacket(capacity=pkt_balanced.capacity_max, energy=-diff)
            self.append_packet_left(PacketType.EXCESS, pkt_residual)

        # 5. Store Balanced
        self.append_packet(PacketType.BALANCED, pkt_balanced)



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

    index_target: int = None
    indices_to_shift: List[int|None] = field(default_factory=list)
    capacities_for_shift: List[float] = field(default_factory=list)


    def balance_group(self, ctx: Context):
        """
        Balancing a group is only required for group_type==UNDEFINED and will only need to check the very first phase pair at index_start.
        """
        if self.group_type == PacketType.BALANCED:
            if DEBUG_LOG: print(f'Nothing to balance.')
            self.indices_to_shift = []
            self.capacities_for_shift = []
            return

        if self.group_type == PacketType.DEFICIT or self.group_type == PacketType.EXCESS:
            if DEBUG_LOG: print(f'A group of type {self.group_type} cannot be balanced!')
            raise

        if DEBUG_LOG: print(f'Balancing group: {self}')
        phase_pair = ctx.phase_pairs[self.index_start]

        while phase_pair.phase_type == PacketType.UNDEFINED:
            phase_pair.balance_packet()

        self.group_type = ctx.phase_pairs[self.index_start].phase_type


        match self.group_type:
            case PacketType.BALANCED:
                self.indices_to_shift = [None]
                self.capacities_for_shift = [ctx.phase_pairs[self.index_start].energy_packets[PacketType.BALANCED][-1].capacity_max]
            case _:
                self.indices_to_shift = [self.index_start]
                self.capacities_for_shift = [ctx.phase_pairs[self.index_start].energy_packets[self.group_type][0].capacity]


        if DEBUG_LOG: print(f'Now: {self}')


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
        if DEBUG_LOG: print(f'Merging:\n  - {self} and\n  - {other}')

        new_type, reason = PhaseGroup._merge_rules[(self.group_type, other.group_type)]

        if new_type is None:
            return False, reason

        self.group_type = new_type

        """Merging two groups will allways set the end index of the first one to the end index of the second one."""
        self.index_end = other.index_end

        if self.group_type == PacketType.BALANCED and other.group_type == PacketType.BALANCED and self.capacities_for_shift[-1] + EPS < other.capacities_for_shift[-1]:
            self.capacities_for_shift[-1] = other.capacities_for_shift[-1]
        else:
            self.indices_to_shift.extend(other.indices_to_shift)
            self.capacities_for_shift.extend(other.capacities_for_shift)

        if DEBUG_LOG: print(f'Merge result:\n  - {self}')
        return True, reason


    def shift(self, ctx: Context):
        """
        For EXCESS groups we iterate over the indices and capacities in reverse direction and shift the to start of the next group.
        """
        if self.group_type == PacketType.BALANCED:
            if DEBUG_LOG: print(f'Nothing to shift.')
            return

        if self.group_type == PacketType.UNDEFINED:
            raise ValueError("Cannot shift UNDEFINED group")

        if DEBUG_LOG: print(f'Shift for {self}')

        # shift to the start of the same group for DEFICIT and to the start of the next group for EXCESS
        index_target = self.index_start if self.group_type == PacketType.DEFICIT else (self.index_end + 1) % ctx.N_phases
        phase_pair_target =  ctx.phase_pairs[index_target]

        capacity_hurdle = 0.0

        # iterate forward for DEFICIT and backward for EXCESS
        pairs = list(zip(self.indices_to_shift, self.capacities_for_shift))

        if self.group_type == PacketType.EXCESS:
            pairs.reverse()

        for index, capacity in pairs:
            # hurdle must include BALANCED entries too
            capacity_hurdle = max(capacity_hurdle, capacity)
            if DEBUG_LOG: print(f'Hurdle update to {capacity_hurdle}')

            if index is None or index == index_target:
                """Nothing to shift from a BALANCED index or same index"""
                continue

            if DEBUG_LOG: print(f'Shift from {index} to {index_target}')
            phase_pair_source = ctx.phase_pairs[index]
            while phase_pair_source.n_packets[self.group_type] > 0:
                pkt = phase_pair_source.pop_packet_left(self.group_type)
                if DEBUG_LOG: print(f'{capacity_hurdle = }')

                if pkt.capacity < capacity_hurdle - EPS:
                    if DEBUG_LOG: print(f'Packet risen to hurdle capacity.')
                    pkt.capacity = capacity_hurdle

                phase_pair_target.append_packet(self.group_type, pkt)

            if DEBUG_LOG: print('--------------')

        self.group_type = PacketType.UNDEFINED if self.group_type == PacketType.DEFICIT else PacketType.BALANCED
        self.indices_to_shift = []
        self.capacities_for_shift = []
        return True



@dataclass
class Context:
    energy_excess_per_phase_initial: List[float]
    energy_deficit_per_phase_initial: List[float]
    N_phases: int = 0

    phase_pairs: List[PhasePair] = None  # The algorithm will store results in this one

    phase_groups: Deque[PhaseGroup] = None  # The algorithm will work on this one


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
            energy_excess_initial=energy_excess_initial,
            energy_deficit_initial=energy_deficit_initial,
        ) for (energy_excess_initial, energy_deficit_initial) in zip(self.energy_excess_per_phase_initial, self.energy_deficit_per_phase_initial)]

        self.phase_groups = deque([PhaseGroup(
            group_type=PacketType.UNDEFINED,  # A phase-group of type UNDEFINED will need to be balanced first and will then be either EXCESS, DEFICIT, or BALANCED
            index_start=index_phase,
            index_end=index_phase
        ) for index_phase in range(self.N_phases)])


    def short_phases(self) -> str:
        s = ''
        for pg in self.phase_groups:
            if pg.index_start == 0 or pg.index_start > pg.index_end:
                s += '|'
            s += pg.group_type.name[0]
        return s


def balance(ctx):
    if DEBUG_LOG:
        print(f'vvvvvvvvvvvvvvvvv BALANCE vvvvvvvvvvvvvvvvv')
        print(format_phase_table_console(ctx))

    for phase_group in ctx.phase_groups:
        if DEBUG_LOG: print('\n----')
        phase_group.balance_group(ctx)

    if DEBUG_LOG:
        print(format_phase_table_console(ctx))
        print(f'^^^^^^^^^^^^^^^^^^ BALANCE ^^^^^^^^^^^^^^^^^^')

    return ctx.n_unbalanced_excess == 0 or ctx.n_unbalanced_deficit == 0



def merge_groups(ctx: Context) -> None:
    dq = ctx.phase_groups
    if len(dq) < 2:
        return

    if DEBUG_LOG:
        print("vvvvvvvvvvvvvvvvv MERGE vvvvvvvvvvvvvvvvv")
        print(format_phase_table_console(ctx))

    # Number of consecutive adjacency checks that did NOT merge.
    no_merge_streak = 0

    # Loop until either only one group remains or a full cycle produced no merges.
    while len(dq) > 1 and no_merge_streak < len(dq):
        left = dq[0]
        right = dq[1]

        if left.can_merge(right):
            merged, reason = left.merge_with(right)
            # If can_merge() is correct, merged must be True here.
            if not merged:
                raise RuntimeError(f"can_merge was True but merge_with failed: {reason}")

            # Remove dq[1] while keeping dq[0] in place:
            dq.rotate(-1)
            dq.popleft()
            dq.rotate(1)

            # Optional but usually helpful: re-check the predecessor of the merged group sooner.
            # (Brings predecessor to front so we next test (pred, merged).)
            dq.rotate(1)

            no_merge_streak = 0

            if DEBUG_LOG: print(f"Merged: {reason}; now {ctx.short_phases()}")

        else:
            dq.rotate(-1)
            no_merge_streak += 1

            if DEBUG_LOG: print(f"No merge; advance; streak={no_merge_streak}; {ctx.short_phases()}")

    if DEBUG_LOG:
        print(format_phase_table_console(ctx))
        print(f'^^^^^^^^^^^^^^^^^^ MERGE ^^^^^^^^^^^^^^^^^^')


def shift_groups(ctx: Context):
    """Iterate over all phase_groups and shift EXCESS groups to the next DEFICIT group"""
    if DEBUG_LOG:
        print("vvvvvvvvvvvvvvvvv SHIFT vvvvvvvvvvvvvvvvv")
        print(format_phase_table_console(ctx))

    for grp in ctx.phase_groups:
        if DEBUG_LOG: print('\n----')
        grp.shift(ctx)

    if DEBUG_LOG:
        print(format_phase_table_console(ctx))
        print(f'^^^^^^^^^^^^^^^^^^ SHIFT ^^^^^^^^^^^^^^^^^^')

def run_mEfES(ctx: Context):
    done = balance(ctx)
    n_it = 0
    while not done:
        merge_groups(ctx)
        shift_groups(ctx)

        if DEBUG_LOG:
            n_it += 1
            print(f'\n\n ++++++++++++++++ ITERATION {n_it} ++++++++++++++ \n\n')

        done = balance(ctx)
        if DEBUG_LOG: print(f'{done = }')

    print('Result:')
    results_str = format_phase_table_console(ctx)
    print(results_str)
    return results_str


def run_example():
    """
The following example is built to illustrate all relevant corner-cases for **balance -> merge -> shift** on cyclic phase sequences.

We model each phase index `k` as a *phase-pair* consisting of an **excess** packet list and a **deficit** packet list.
Initially, each side contains exactly one packet at capacity 0 with an energy amount given by the input arrays.

During **BALANCE**, a phase-pair is converted from type `U` (undefined) into one of:
- `B` (balanced) if excess == deficit (no split required),
- `E` (excess) if excess > deficit (split the excess packet at `capacity = deficit`),
- `D` (deficit) if deficit > excess (split the deficit packet at `capacity = excess`).

-------------------------------------------------------------------------------
Group types and allowed merges (non-commutative algebra)
-------------------------------------------------------------------------------

There are four possible group types: Undefined (U), Balanced (B), Excess (E), Deficit (D).
Considering ordered tuples `(left, right)` yields 16 combinations, but after BALANCE the sequence is composed of {B, E, D}.

Allowed merges are described by a non-commutative operation `(+)`:

(+)| U | B | D | E |
-- + - | - | - | - |
 U | x | x | x | x |
 B | x | B | D | x |
 D | x | x | D | x |
 E | x | E | x | E |

Interpretation:
- `B (+) B`, `D (+) D`, `E (+) E`:
  Merging adjacent groups of the same type is always allowed.
- `E (+) B`:
  Excess packets will shift to the **right**; we keep the *B* group metadata because it may be required to decide later interactions.
- `B (+) D`:
  Deficit packets will shift to the **left**; we keep the *B* group metadata because it may be required to decide later interactions.

Not allowed:
- Any merge involving `U` (must be balanced first).
- `B (+) E` or `D (+) B`:
  would lose directional information needed for subsequent shifts.
- `E (+) D` or `D (+) E`:
  must undergo shifting first (direct conflict of directions).

-------------------------------------------------------------------------------
Shift corner-cases (what we want to cover)
-------------------------------------------------------------------------------

Shifting moves packets across neighboring groups until no further valid moves exist.

Key “hovering” / interaction scenarios (expressed using the algorithm’s debug terms):
- A shift step compares a packet’s `capacity_hurdle` against the available `capacity_max_target` at the destination.
- If the packet can be integrated into the destination, we report **Packet merged**; otherwise we report **Packet inserted** (hover/pass-over behavior).
- Equality `capacity_hurdle == capacity_max_target` is a critical edge-case that must behave deterministically (no oscillations).

We want to cover, for both directions:
- **insert** with unchanged capacity (pure hover / pass-over),
- **insert** with capacity increase (hurdle lifts the packet even without merging),
- **merge** with unchanged capacity (often the equality case),
- **merge** with capacity increase (true “landing”/integration).

-------------------------------------------------------------------------------
Concrete example (current regression/illustration input + observed behavior)
-------------------------------------------------------------------------------

Initial energies per phase (capacity-0 packets):
    energy_excess_per_phase_initial  = [40, 3, 10, 20, 60, 3, 1, 50, 2, 5, 2, 7, 2, 50, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [40, 5, 10, 20, 60, 2, 2, 50, 3, 8, 3, 5, 1, 50, 1, 2, 1, 5]

BALANCE produces the initial group-type sequence:
    index:  0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17
    type :  B D B B B E D B D D  D  E  E  B  E  D  E  E
    ==> "BDBBBEDBDDDEEBEDEE"

MERGE coverage observed in this run:
- `B (+) D` at the cycle boundary is exercised immediately:
  (0:B) merges with (1:D) into (0..1:D), reason: `DEFICIT will be shifted left over BALANCE.`
- `B (+) B` is exercised twice:
  (2:B)+(3:B) -> (2..3:B), then (2..3:B)+(4:B) -> (2..4:B), reason: `Same type`.
- `D (+) D` collapses the deficit chain:
  (6:D)+(7..8:D)+(9:D)+(10:D) -> (6..10:D), reason: `Same type`.
- `E (+) E` collapses adjacent excess groups:
  (11:E)+(12:E) -> (11..12:E) and (16:E)+(17:E) -> (16..17:E), reason: `Same type`.
- `E (+) B` is exercised:
  (11..12:E)+(13:B) -> (11..13:E), reason: `EXCESS will be shifted right over BALANCE.`
- After the first SHIFT and re-BALANCE, MERGE further collapses the structure to `B | E | D`.

SHIFT coverage observed in this run (as printed):
- Excess shifting right across the 17->0 boundary:
  Shift from 17 to 0` and `Shift from 16 to 0` with a subsequent packet risen to hurdle capacity.
- Deficit shifting left within the large D-group (6..10):
  hurdle updates `1 -> 2 -> 5` and shifts `8 -> 6`, `9 -> 6`, `10 -> 6`, with a `Packet risen to hurdle capacity.` at the end.
- Excess shifting right from the large E-group (11..14) into 15:
  shifts `14 -> 15`, `12 -> 15`, `11 -> 15` with hurdle updates `1, 1, 5`.

Convergence / end state (as in the log):
- The algorithm executes a second BALANCE/MERGE/SHIFT cycle.
- In the final BALANCE, the remaining `U` group (6..10) becomes `E` with
  `capacities_for_shift=[12]`, and the run terminates with `done = True`.
- The final printed “Result” table matches a reduced configuration dominated by BALANCED groups plus a single EXCESS group (6..10), demonstrating that this input triggers the intended merge and shift branches without instability.

This example is used as a regression/illustration case to ensure:
- legal merges are exercised (notably `B (+) B`, which was previously missing),
- directional merges `E (+) B` and `B (+) D` occur with the expected reasons,
- SHIFT demonstrates hurdle updates and capacity lifting (`Packet risen to hurdle capacity.`), including wrap-around behavior across the cyclic boundary.

The end result will be:
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
      |                           B                            ||                                                               :B                                                                ||                                    E                                     |
      |     11      |     12      |      13      |     14      ||     15      |     16      |     17      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8      |      9      |     10      |
      | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  3   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,5 |   |   | 0,1 |   |   | 0,50 |   |   | 0,1 |   ||   | 0,2 |   |   | 0,1 |   |   | 0,5 |   |   | 0,42 |   |   | 0,3 |   |   | 0,10 |   |   | 0,20 |   |   | 0,60 |   |   | 0,2 |   || 55,2 | 0,1  |   |   | 0,50 |   |   | 0,2 |   |   | 0,5 |   |   | 0,2 |   |
ep[1] |   |     |   |   |     |   |   |      |   |   |     |   ||   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 2,1  |   |   |      |   |   |     |   |   |     |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |      |   |   |     |   ||   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 50,5 |   |   |      |   |   |     |   |   |     |   |   |     |   |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    global DEBUG_LOG
    DEBUG_LOG = True

    energy_excess_per_phase_initial = [40, 3, 10, 20, 60, 3, 1, 50, 2, 5, 2, 7, 2, 50, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [40, 5, 10, 20, 60, 2, 2, 50, 3, 8, 3, 5, 1, 50, 1, 2, 1, 5]

    result_ref = """
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
      |                           B                            ||                                                               :B                                                                ||                                    E                                     |
      |     11      |     12      |      13      |     14      ||     15      |     16      |     17      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8      |      9      |     10      |
      | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  3   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,5 |   |   | 0,1 |   |   | 0,50 |   |   | 0,1 |   ||   | 0,2 |   |   | 0,1 |   |   | 0,5 |   |   | 0,42 |   |   | 0,3 |   |   | 0,10 |   |   | 0,20 |   |   | 0,60 |   |   | 0,2 |   || 55,2 | 0,1  |   |   | 0,50 |   |   | 0,2 |   |   | 0,5 |   |   | 0,2 |   |
ep[1] |   |     |   |   |     |   |   |      |   |   |     |   ||   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 2,1  |   |   |      |   |   |     |   |   |     |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |      |   |   |     |   ||   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 50,5 |   |   |      |   |   |     |   |   |     |   |   |     |   |
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    ctx = Context(energy_excess_per_phase_initial=energy_excess_per_phase_initial, energy_deficit_per_phase_initial=energy_deficit_per_phase_initial)
    result = run_mEfES(ctx)
    print('\n' + result + '\n' == result_ref)



def run_random_examples(N_Phases:int):
    from random import random
    energy_excess_per_phase_initial = [random() for _ in range(N_Phases)]
    energy_deficit_per_phase_initial = [random() for _ in range(N_Phases)]
    ctx = Context(energy_excess_per_phase_initial=energy_excess_per_phase_initial, energy_deficit_per_phase_initial=energy_deficit_per_phase_initial)
    result = run_mEfES(ctx)


PHASE_COL_TYPES = (PacketType.EXCESS, PacketType.BALANCED, PacketType.DEFICIT)

def _pp_get_pkts(pp: PhasePair, tp: PacketType):
    # Backward-compatible: missing BALANCED -> empty deque
    try:
        return pp.energy_packets[tp]
    except KeyError:
        return deque()


def _pp_get_n(pp: PhasePair, tp: PacketType) -> int:
    # Prefer new API
    if hasattr(pp, "n_packets"):
        return int(pp.n_packets.get(tp, 0))
    # Fallback to old API
    if tp == PacketType.BALANCED:
        return 0
    return int(pp.n_packets.get(tp, 0))


def _fmt_num(x: float) -> str:
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return f"{x:g}"


def _fmt_packet(pkt: EnergyPacket) -> str:
    return f"{_fmt_num(pkt.capacity)},{_fmt_num(pkt.energy)}"


def _iter_group_indices(index_start: int, index_end: int, n_phases: int) -> Iterable[int]:
    if index_end is None:
        index_end = index_start
    if index_start <= index_end:
        yield from range(index_start, index_end + 1)
    else:
        yield from range(index_start, n_phases)
        yield from range(0, index_end + 1)


def _group_marker(pg: PhaseGroup) -> str:
    prefix = ":" if (pg.index_start == 0 or (pg.index_end is not None and pg.index_start > pg.index_end)) else ""
    return f"{prefix}{pg.group_type.name[0]}"  # B/E/D/U (upper)


def _build_phase_order_and_groups(ctx: "Context") -> tuple[list[int], list[tuple[str, list[int]]]]:
    """
    Returns:
      - phase_order: flattened phase indices in current group order (deduped)
      - groups: list of (group_marker, indices_in_that_group_after_dedup)
    """
    n = ctx.N_phases
    seen: set[int] = set()

    phase_order: list[int] = []
    groups: list[tuple[str, list[int]]] = []

    for pg in ctx.phase_groups:
        raw = list(_iter_group_indices(pg.index_start, pg.index_end, n))
        kept = []
        for i in raw:
            if i in seen:
                continue
            seen.add(i)
            kept.append(i)
            phase_order.append(i)
        if kept:
            groups.append((_group_marker(pg), kept))

    return phase_order, groups


def format_phase_table_console(ctx: "Context") -> str:
    """
    3 columns per phase: (i,E), (i,D), (i,B).
    Header merging:
      - group row merged across each group's columns
      - index row merged across the 3 columns of each phase
    Visual boundaries:
      - group boundaries rendered as '||' between groups (all rows)
    Row order: group, index, phase type, n, ep[...]
    """
    phase_order, groups = _build_phase_order_and_groups(ctx)
    n_types = len(PHASE_COL_TYPES)

    # column specs: (phase_index, packet_type)
    col_specs: list[tuple[int, PacketType]] = []
    for i in phase_order:
        for tp in PHASE_COL_TYPES:
            col_specs.append((i, tp))

    # group boundary positions (between columns)
    boundary_after_col: set[int] = set()
    col_cursor = 0
    for _marker, idxs in groups:
        span = n_types * len(idxs)
        boundary_after_col.add(col_cursor + span - 1)
        col_cursor += span

    # boundary after phase segments for merged index row (segments are phases)
    boundary_after_phase_seg: set[int] = set()
    phase_cursor = 0
    for _marker, idxs in groups:
        boundary_after_phase_seg.add(phase_cursor + len(idxs) - 1)
        phase_cursor += len(idxs)

    # per-column rows
    type_map = {PacketType.EXCESS: "e", PacketType.DEFICIT: "d", PacketType.BALANCED: "b"}
    type_row: list[str] = [type_map[tp] for (_i, tp) in col_specs]
    n_row: list[str] = [str(_pp_get_n(ctx.phase_pairs[i], tp)) for (i, tp) in col_specs]

    # packet rows
    max_k = 0
    for i in phase_order:
        pp = ctx.phase_pairs[i]
        for tp in PHASE_COL_TYPES:
            max_k = max(max_k, len(_pp_get_pkts(pp, tp)))

    ep_rows: list[tuple[str, list[str]]] = []
    for k in range(max_k):
        row = []
        for i, tp in col_specs:
            pkts = _pp_get_pkts(ctx.phase_pairs[i], tp)
            row.append(_fmt_packet(pkts[k]) if k < len(pkts) else "")
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

    def _render_segments(label: str, segments: list[tuple[str, int]], thick_after_seg: set[int] | None = None) -> str:
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
    for marker, idxs in groups:
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

    lines = [
        _render_segments("", group_segments, thick_after_seg=thick_after_group_seg),
        _render_segments("", index_segments, thick_after_seg=boundary_after_phase_seg),
        _render_unmerged("", type_row),
    ]

    sep = "-" * len(lines[0])

    out = [
        sep,
        lines[0],
        lines[1],
        lines[2],
        sep,
        _render_unmerged("n", n_row),
        sep,
        *[_render_unmerged(lbl, cells) for (lbl, cells) in ep_rows],
        sep,
    ]
    return "\n".join(out)


def format_phase_table_latex(ctx: "Context") -> str:
    """
    LaTeX-ish output using \\multicolumn for merged group + index rows.
    3 columns per phase: E, D, B.
    Row order: group, index, phase type, n, ep[...]
    """
    phase_order, groups = _build_phase_order_and_groups(ctx)
    n_types = len(PHASE_COL_TYPES)

    # group row: multicolumn over n_types*len(group)
    group_cells = []
    for marker, idxs in groups:
        span = n_types * len(idxs)
        group_cells.append(rf"\multicolumn{{{span}}}{{c}}{{{marker}}}")

    # index row: each phase spans n_types columns
    idx_cells = [rf"\multicolumn{{{n_types}}}{{c}}{{{i}}}" for i in phase_order]

    # phase type row: per column
    type_map = {PacketType.EXCESS: "e", PacketType.DEFICIT: "d", PacketType.BALANCED: "b"}
    type_cells = []
    for _i in phase_order:
        type_cells.extend([type_map[tp] for tp in PHASE_COL_TYPES])

    # n row: per column
    n_cells = []
    for i in phase_order:
        pp = ctx.phase_pairs[i]
        for tp in PHASE_COL_TYPES:
            n_cells.append(str(_pp_get_n(pp, tp)))

    # ep rows
    max_k = 0
    for i in phase_order:
        pp = ctx.phase_pairs[i]
        for tp in PHASE_COL_TYPES:
            max_k = max(max_k, len(_pp_get_pkts(pp, tp)))

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
            pp = ctx.phase_pairs[i]
            for tp in PHASE_COL_TYPES:
                pkts = _pp_get_pkts(pp, tp)
                cells.append(_fmt_packet(pkts[k]) if k < len(pkts) else "")
        rows.append(latex_row(f"ep[{k}]", cells))

    return "\n".join(rows)




if __name__ == '__main__':
    run_example()

    #run_random_examples(100)
    #for N_phases in range(0,100,10):
    #    run_random_examples(N_phases)

