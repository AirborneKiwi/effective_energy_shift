from __future__ import annotations

from enum import Enum
from collections import deque
from dataclasses import dataclass, field, InitVar
from typing import Deque, List, Set, Dict, Tuple, Iterable


class PacketType(Enum):
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



@dataclass
class PhasePair:
    """ A phase pair consists of excess energy packets and deficit energy packets belonging to exaxtly one excess phase and one deficit phase.
    """
    energy_packets: Dict[PacketType, Deque[EnergyPacket]] = field(default_factory=lambda: {PacketType.EXCESS: deque(), PacketType.DEFICIT: deque()})
    n_unbalanced: Dict[PacketType, int] = field(default_factory = lambda: {PacketType.EXCESS: 0, PacketType.DEFICIT: 0})
    N_unbalanced_total: int = 0

    energy_excess_initial: InitVar[float | None] = None
    energy_deficit_initial: InitVar[float | None] = None

    def __post_init__(self, energy_excess_initial: float, energy_deficit_initial: float):
        self.insert_packet(
            index_packet=0,
            packet_type=PacketType.EXCESS,
            energy_packet=EnergyPacket(capacity=0, energy=energy_excess_initial)
        )
        self.insert_packet(
            index_packet=0,
            packet_type=PacketType.DEFICIT,
            energy_packet=EnergyPacket(capacity=0, energy=energy_deficit_initial)
        )


    @property
    def phase_type(self):
        if self.n_unbalanced[PacketType.EXCESS] == 0 and self.n_unbalanced[PacketType.DEFICIT] == 0:
            return PacketType.BALANCED

        if self.n_unbalanced[PacketType.EXCESS] >= 1 and self.n_unbalanced[PacketType.DEFICIT] >= 1:
            return PacketType.UNDEFINED

        if self.n_unbalanced[PacketType.EXCESS] >= 1:
            return PacketType.EXCESS

        if self.n_unbalanced[PacketType.DEFICIT] >= 1:
            return PacketType.DEFICIT

        raise


    def capacity_max_at_tail(self, packet_type: PacketType) -> float:
        n_u = self.n_unbalanced[packet_type]
        idx = (n_u - 1) if n_u > 0 else -1
        return self.energy_packets[packet_type][idx].capacity_max


    def remove_packet(self, index_packet: int, packet_type: PacketType ):
        """Removes an energy packet of packet_type at index_packet from the phase pair.
        Rotate left by index_packet is O(index_packet), pop left O(1) and rotate right by index_packet O(index_packet)
        """
        self.energy_packets[packet_type].rotate(-index_packet)
        self.energy_packets[packet_type].popleft()
        self.energy_packets[packet_type].rotate( index_packet)

        self.n_unbalanced[packet_type] -= 1  # reduce the number of unbalanced packets
        self.N_unbalanced_total -= 1
        assert self.N_unbalanced_total >= 0

    def insert_packet(self, index_packet: int, packet_type: PacketType, energy_packet: EnergyPacket ):
        """Inserts an energy packet of packet_type at index_packet to the phase pair.
        Rotate left by index_packet is O(index_packet), append left O(1) and rotate right by index_packet O(index_packet)
        """
        self.energy_packets[packet_type].rotate(-index_packet)
        self.energy_packets[packet_type].appendleft(energy_packet)
        self.energy_packets[packet_type].rotate( index_packet)

        self.n_unbalanced[packet_type] += 1  # increase the number of unbalanced packets
        self.N_unbalanced_total += 1


    def balance_packet(self):
        self.n_unbalanced[PacketType.EXCESS] -= 1
        self.n_unbalanced[PacketType.DEFICIT] -= 1
        self.N_unbalanced_total -= 2

        assert self.N_unbalanced_total >= 0

        # rotate the packet-tuples left to move the now balanced packet to the end of the deque
        self.energy_packets[PacketType.EXCESS].rotate(-1)
        self.energy_packets[PacketType.DEFICIT].rotate(-1)


    def merge_packets(self, packet_type: PacketType):
        EPS = 1e-12
        while self.n_unbalanced[packet_type] > 1 and self.energy_packets[packet_type][0].capacity_max + EPS >= self.energy_packets[packet_type][1].capacity:
            print(f'Merging packets of type {packet_type}')
            print(f'Before: {self.energy_packets[packet_type]}')
            self.energy_packets[packet_type][0].energy += self.energy_packets[packet_type][1].energy  # combine the energy content

            # remove the merged packet
            self.remove_packet(
                index_packet=1,
                packet_type=packet_type
            )

            print(f'Now: {self.energy_packets[packet_type]}')


    def split_packet(self, index_packet: int, packet_type: PacketType, capacity_to_split: float):
        EPS = 1e-12
        if capacity_to_split <= self.energy_packets[packet_type][index_packet].capacity + EPS or self.energy_packets[packet_type][index_packet].capacity_max - EPS <= capacity_to_split:
            return  # we can only split a packet, when the capacity value lies within the packet

        print(f'Splitting packet of type {packet_type} at {capacity_to_split}')
        print(f'Before: {self.energy_packets[packet_type]}')

        energy_new_packet = self.energy_packets[packet_type][index_packet].capacity_max - capacity_to_split  # calculate the remaining energy content
        self.energy_packets[packet_type][index_packet].energy = capacity_to_split - self.energy_packets[packet_type][index_packet].capacity  # calculate the lower packets energy content.

        # insert the new packet at index 1
        self.insert_packet(
            index_packet=index_packet+1,
            packet_type=packet_type,
            energy_packet=EnergyPacket(
                capacity=capacity_to_split,
                energy=energy_new_packet
            )
        )

        print(f'Now: {self.energy_packets[packet_type]}')



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
            print(f'Nothing to balance.')
            return

        if self.group_type == PacketType.DEFICIT or self.group_type == PacketType.EXCESS:
            print(f'A group of type {self.group_type} cannot be balanced!')
            raise

        print(f'Balancing group: {self}')
        while ctx.phase_pairs[self.index_start].n_unbalanced[PacketType.EXCESS] > 0 and ctx.phase_pairs[self.index_start].n_unbalanced[PacketType.DEFICIT] > 0:
            # The earliest available capacity is the maximum of both packets. Raise packets to the earliest available capacity which might touch the next energy packets of the same kind.
            capacity_earliest_available = max( ctx.phase_pairs[self.index_start].energy_packets[PacketType.EXCESS][0].capacity, ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][0].capacity )

            if ctx.phase_pairs[self.index_start].energy_packets[PacketType.EXCESS][0].capacity < capacity_earliest_available:
                ctx.phase_pairs[self.index_start].energy_packets[PacketType.EXCESS][0].capacity = capacity_earliest_available
                ctx.phase_pairs[self.index_start].merge_packets(PacketType.EXCESS)  # Merge and potentially remove packets.

            if ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][0].capacity < capacity_earliest_available:
                ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][0].capacity = capacity_earliest_available
                ctx.phase_pairs[self.index_start].merge_packets(PacketType.DEFICIT)  # Merge and potentially remove packets.

            # Balance excess and deficit by computing the minimum of both energy contents and create a new packet with the remaining content.
            capacity_max_excess = ctx.phase_pairs[self.index_start].energy_packets[PacketType.EXCESS][0].capacity_max
            capacity_max_deficit = ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][0].capacity_max
            capacity_to_split = min( capacity_max_excess, capacity_max_deficit )

            if capacity_max_excess > capacity_to_split:  # excess remaining
                # Split will create a new unbalanced energy packet
                ctx.phase_pairs[self.index_start].split_packet(index_packet=0, packet_type=PacketType.EXCESS, capacity_to_split=capacity_to_split)
            elif capacity_max_deficit > capacity_to_split:  # deficit remaining
                # Split will create a new unbalanced energy packet
                ctx.phase_pairs[self.index_start].split_packet(index_packet=0, packet_type=PacketType.DEFICIT, capacity_to_split=capacity_to_split)

            ctx.phase_pairs[self.index_start].balance_packet()


        self.group_type = ctx.phase_pairs[self.index_start].phase_type


        match self.group_type:
            case PacketType.BALANCED:
                self.indices_to_shift = [None]
                self.capacities_for_shift = [ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][-1].capacity_max]
            case PacketType.EXCESS:
                self.indices_to_shift = [self.index_start]
                self.capacities_for_shift = [ctx.phase_pairs[self.index_start].energy_packets[PacketType.EXCESS][0].capacity]
            case PacketType.DEFICIT:
                self.indices_to_shift = [self.index_start]
                self.capacities_for_shift = [ctx.phase_pairs[self.index_start].energy_packets[PacketType.DEFICIT][0].capacity]


        print(f'Now: {self}')


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
        print(f'Merging:\n  - {self} and\n  - {other}')

        new_type, reason = PhaseGroup._merge_rules[(self.group_type, other.group_type)]

        if new_type is None:
            return False, reason

        self.group_type = new_type

        """Merging two groups will allways set the end index of the first one to the end index of the second one."""
        self.index_end = other.index_end
        self.indices_to_shift.extend(other.indices_to_shift)
        self.capacities_for_shift.extend(other.capacities_for_shift)

        print(f'Merge result:\n  - {self}')
        return True, reason


    def shift(self, ctx: Context):
        """
        For EXCESS groups we iterate over the indices and capacities in reverse direction and shift the to start of the next group.
        """
        if self.group_type == PacketType.BALANCED:
            print(f'Nothing to shift.')
            return

        if self.group_type == PacketType.UNDEFINED:
            raise ValueError("Cannot shift UNDEFINED group")

        print(f'Shift for {self}')

        # shift to the start of the same group for DEFICIT and to the start of the next group for EXCESS
        index_target = self.index_start if self.group_type == PacketType.DEFICIT else (self.index_end + 1) % ctx.N_phases

        phase_pair_target =  ctx.phase_pairs[index_target]
        capacity_hurdle = 0

        # iterate forward for DEFICIT and backward for EXCESS
        pairs = list(zip(self.indices_to_shift, self.capacities_for_shift))
        if self.group_type == PacketType.EXCESS:
            pairs.reverse()

        for index, capacity in pairs:
            # hurdle must include BALANCED entries too
            capacity_hurdle = max(capacity_hurdle, capacity)
            print(f'Hurdle update to {capacity_hurdle}')

            if index is None or index == index_target:
                """Nothing to shift from a BALANCED index or same index"""
                continue

            print(f'Shift from {index} to {index_target}')
            while ctx.phase_pairs[index].n_unbalanced[self.group_type] > 0:
                # "last relevant" packet at target: if any unbalanced, last-unbalanced; else last (balanced)
                n_unbalanced = phase_pair_target.n_unbalanced[self.group_type]

                capacity_max_target = phase_pair_target.capacity_max_at_tail(self.group_type)

                print(f'{capacity_max_target = }')
                print(f'{capacity_hurdle = }')
                pkt = ctx.phase_pairs[index].energy_packets[self.group_type][0]
                print(f'Packet capacity before shift is {pkt.capacity}')
                pkt.capacity = max(pkt.capacity, capacity_max_target, capacity_hurdle)
                print(f'Packet capacity after shift is {pkt.capacity}')

                EPS = 1e-12
                # float-safe merge decision
                if n_unbalanced > 0 and abs(pkt.capacity == capacity_max_target) <= EPS:
                    # merge packets
                    print('Packet merged')
                    phase_pair_target.energy_packets[self.group_type][n_unbalanced - 1].energy += pkt.energy
                else:
                    # insert packet
                    print('Packet inserted')
                    phase_pair_target.insert_packet(
                        index_packet=n_unbalanced, # append to unbalanced tail
                        packet_type=self.group_type,
                        energy_packet=pkt
                    )

                ctx.phase_pairs[index].remove_packet(
                    index_packet=0,
                    packet_type=self.group_type
                )

            print('--------------')

        self.group_type = PacketType.UNDEFINED if self.group_type == PacketType.DEFICIT else PacketType.BALANCED
        self.indices_to_shift = []
        self.capacities_for_shift = []
        return True



@dataclass
class Context:
    energy_excess_per_phase_initial: List[float]
    energy_deficit_per_phase_initial: List[float]
    N_phases: int = 0

    phase_pairs: Deque[PhasePair] = None  # The algorithm will store results in this one

    phase_groups: Deque[PhaseGroup] = None  # The algorithm will work on this one

    indices_to_balance: Deque[int] = None
    indices_first_and_last: Dict[PacketType, List[int]] = field(default_factory=lambda: {PacketType.EXCESS: [None, None], PacketType.DEFICIT: [None, None]})

    @property
    def N_unbalanced_total(self):
        return sum([phase_pair.N_unbalanced_total for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_excess(self):
        return sum([phase_pair.n_unbalanced[PacketType.EXCESS] for phase_pair in self.phase_pairs])

    @property
    def n_unbalanced_deficit(self):
        return sum([phase_pair.n_unbalanced[PacketType.DEFICIT] for phase_pair in self.phase_pairs])


    def __post_init__(self):
        assert len(self.energy_excess_per_phase_initial) == len(self.energy_deficit_per_phase_initial)

        self.N_phases = len(self.energy_deficit_per_phase_initial)

        self.indices_to_balance = deque(range(self.N_phases))

        self.phase_pairs = deque([PhasePair(
            energy_excess_initial=energy_excess_initial,
            energy_deficit_initial=energy_deficit_initial,
        ) for (energy_excess_initial, energy_deficit_initial) in zip(self.energy_excess_per_phase_initial, self.energy_deficit_per_phase_initial)])

        self.phase_groups = deque([PhaseGroup(
            group_type=PacketType.UNDEFINED,  # A phase-group of type UNDEFINED will need to be balanced first and will then be either EXCESS, DEFICIT, or BALANCED
            index_start=index_phase,
            index_end=index_phase
        ) for index_phase in range(self.N_phases)])


    def print_phase_groups(self) -> str:
        short_dict = {}
        for pg in self.phase_groups:
            _ = {(pg.index_start, pg.index_end): pg.group_type.name}
            short_dict.update(_)
        return str(short_dict)

    def short_phases(self) -> str:
        s = ''
        for pg in self.phase_groups:
            if pg.index_start == 0 or pg.index_start > pg.index_end:
                s += '|'
            s += pg.group_type.name[0]
        return s


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
    prefix = "|" if (pg.index_start == 0 or (pg.index_end is not None and pg.index_start > pg.index_end)) else ""
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
    2 columns per phase: (i,E) and (i,D).
    Header merging:
      - group row merged across each group's columns
      - index row merged across the 2 columns of each phase
    Visual boundaries:
      - group boundaries rendered as '||' between groups (all rows)
    Row order: group, index, phase type, n, ep[...]
    """
    phase_order, groups = _build_phase_order_and_groups(ctx)

    # column specs: (phase_index, packet_type)
    col_specs: list[tuple[int, PacketType]] = []
    for i in phase_order:
        col_specs.append((i, PacketType.EXCESS))
        col_specs.append((i, PacketType.DEFICIT))

    # group boundary positions (between columns)
    # boundary_after_col contains the *column index* after which we place a thick separator.
    boundary_after_col: set[int] = set()
    col_cursor = 0
    for _marker, idxs in groups:
        span = 2 * len(idxs)
        boundary_after_col.add(col_cursor + span - 1)  # last col of this group
        col_cursor += span

    # also boundary after phase-segments for the merged index row (segments are phases)
    boundary_after_phase_seg: set[int] = set()
    phase_cursor = 0
    for _marker, idxs in groups:
        boundary_after_phase_seg.add(phase_cursor + len(idxs) - 1)  # last phase of group
        phase_cursor += len(idxs)

    # per-column rows
    type_row: list[str] = [("e" if tp == PacketType.EXCESS else "d") for (_, tp) in col_specs]
    n_row: list[str] = [str(ctx.phase_pairs[i].n_unbalanced[tp]) for (i, tp) in col_specs]

    # packet rows
    max_k = 0
    for i in phase_order:
        max_k = max(max_k, len(ctx.phase_pairs[i].energy_packets[PacketType.EXCESS]))
        max_k = max(max_k, len(ctx.phase_pairs[i].energy_packets[PacketType.DEFICIT]))

    ep_rows: list[tuple[str, list[str]]] = []
    for k in range(max_k):
        row = []
        for i, tp in col_specs:
            pkts = ctx.phase_pairs[i].energy_packets[tp]
            row.append(_fmt_packet(pkts[k]) if k < len(pkts) else "")
        ep_rows.append((f"ep[{k}]", row))

    # widths derived from non-merged rows
    base_rows_for_widths: list[list[str]] = [type_row, n_row] + [r for _, r in ep_rows]
    col_ws = [max((len(r[c]) for r in base_rows_for_widths), default=0) for c in range(len(col_specs))]
    label_w = max(len("n"), *(len(lbl) for lbl, _ in ep_rows), 0)

    def _span_width(c0: int, span_cols: int) -> int:
        # width of merged segment equals sum(col widths) + 3*(span_cols-1) for internal thin separators
        return sum(col_ws[c0:c0 + span_cols]) + 3 * (span_cols - 1)

    def _cell(text: str, width: int) -> str:
        return f"{text:^{width}}"

    def _render_segments(label: str, segments: list[tuple[str, int]], thick_after_seg: set[int] | None = None) -> str:
        """segments are already merged blocks; separators happen between segments."""
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
        """cells are per-column; insert '||' after group boundary columns."""
        left = f"{label:<{label_w}}"
        out = [left, " | "]
        for c, cell in enumerate(cells):
            out.append(_cell(cell, col_ws[c]))
            if c != len(cells) - 1:
                out.append(" || " if c in boundary_after_col else " | ")
        out.append(" |")
        return "".join(out)

    # ---- merged header rows
    # Group row: segments per group; thick separators between every group segment
    group_segments: list[tuple[str, int]] = []
    c = 0
    for marker, idxs in groups:
        span = 2 * len(idxs)
        group_segments.append((marker, _span_width(c, span)))
        c += span
    thick_after_group_seg = set(range(len(group_segments) - 1))  # thick between all groups

    # Index row: segments per phase (span=2); thick at group boundaries only
    index_segments: list[tuple[str, int]] = []
    c = 0
    for i in phase_order:
        index_segments.append((str(i), _span_width(c, 2)))
        c += 2

    # Phase type row: unmerged (per column)
    # n row: unmerged (per column)
    # ep rows: unmerged (per column)

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
    Row order: group, index, phase type, n, ep[...]
    """
    phase_order, groups = _build_phase_order_and_groups(ctx)

    # group row: multicolumn over 2*len(group)
    group_cells = []
    for marker, idxs in groups:
        span = 2 * len(idxs)
        group_cells.append(rf"\multicolumn{{{span}}}{{c}}{{{marker}}}")

    # index row: each phase spans 2 columns
    idx_cells = [rf"\multicolumn{{2}}{{c}}{{{i}}}" for i in phase_order]

    # phase type row: per column (lowercase)
    type_cells = []
    for _i in phase_order:
        type_cells.extend(["e", "d"])

    # n row: per column
    n_cells = []
    for i in phase_order:
        n_cells.append(str(ctx.phase_pairs[i].n_unbalanced[PacketType.EXCESS]))
        n_cells.append(str(ctx.phase_pairs[i].n_unbalanced[PacketType.DEFICIT]))

    # ep rows
    max_k = 0
    for i in phase_order:
        max_k = max(max_k, len(ctx.phase_pairs[i].energy_packets[PacketType.EXCESS]))
        max_k = max(max_k, len(ctx.phase_pairs[i].energy_packets[PacketType.DEFICIT]))

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
            ex = ctx.phase_pairs[i].energy_packets[PacketType.EXCESS]
            de = ctx.phase_pairs[i].energy_packets[PacketType.DEFICIT]
            cells.append(_fmt_packet(ex[k]) if k < len(ex) else "")
            cells.append(_fmt_packet(de[k]) if k < len(de) else "")
        rows.append(latex_row(f"ep[{k}]", cells))

    return "\n".join(rows)




def balance(ctx):
    print(f'=============== BALANCE ===============')
    print(format_phase_table_console(ctx))
    for phase_group in ctx.phase_groups:
        print('\n----')
        phase_group.balance_group(ctx)

    return ctx.n_unbalanced_excess == 0 or ctx.n_unbalanced_deficit == 0



def merge_groups(ctx: Context):
    print(f'=============== MERGE ===============')
    print(format_phase_table_console(ctx))
    n_rotations_total = len(ctx.phase_groups)
    n_rotated = 0
    while n_rotated < n_rotations_total:

        print('\n----')
        str_original_0 = ctx.short_phases()

        ctx.phase_groups[-1].can_merge(ctx.phase_groups[0])

        while ctx.phase_groups[-1].can_merge(ctx.phase_groups[0]):
            ctx.phase_groups.rotate(1)
            n_rotations_total += 1
            print('rotated back by 1')

        str_original = ctx.short_phases()
        merged, reason = ctx.phase_groups[0].merge_with(ctx.phase_groups[1])

        if merged:
            print(f'Merge possible: {reason}')
            ctx.phase_groups.rotate(-1)
            ctx.phase_groups.popleft()
            ctx.phase_groups.rotate(1)
            n_rotations_total -= 1
        else:
            print(f"Can't merge: {reason}")
            ctx.phase_groups.rotate(-1)
            n_rotated += 1

        str_after = ctx.short_phases()

        print(f'{str_original_0} -> {str_original} -> {str_after}  ({"same length" if len(str_original) == len(str_after) else "1 merged"})')

    print('')


def shift_groups(ctx: Context):
    """Iterate over all phase_groups and shift EXCESS groups to the next DEFICIT group"""
    print(f'=============== SHIFT ===============')
    print(format_phase_table_console(ctx))
    for grp in ctx.phase_groups:
        print('\n----')
        grp.shift(ctx)


def run_mEfES(ctx: Context):
    done = balance(ctx)
    while not done:
        merge_groups(ctx)
        shift_groups(ctx)

        print('\n\n +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n\n')

        done = balance(ctx)
        print(f'{done = }')

    print('Result:')
    print(format_phase_table_console(ctx))


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
    energy_excess_per_phase_initial  = [4, 3, 3, 2, 6, 3, 1, 2, 2, 5, 2, 7, 2, 1, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [4, 5, 3, 2, 6, 2, 2, 2, 3, 8, 3, 5, 1, 1, 1, 2, 1, 5]

BALANCE produces the initial group-type sequence:
    index:  0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17
    type :  B D B B B E D B D D  D  E  E  B  E  D  E  E
    ==> "BDBBBEDBDDDEEBEDEE"

MERGE coverage observed in this example:
- Same-type merges:
  - `E (+) E`: e.g. indices 16 and 17 merge into a single E-group.
  - `D (+) D`: deficits (6..10) merge into a single D-group over multiple steps.
  - `B (+) B`: balanced (2,3) merge and then merge with (4) into a single B-group (2..4).
- Directed merges:
  - `E (+) B`: exercised multiple times (EXCESS will be shifted right over BALANCE).
  - `B (+) D`: exercised (DEFICIT will be shifted left over BALANCE).
- Forbidden merges are explicitly attempted and rejected:
  - `E (+) D` / `D (+) E`: “needs to undergo shifting first.”
  - `B (+) E` / `D (+) B`: “would lose information for potential later shift operations.”

SHIFT coverage observed in this example (selected highlights from the debug log):
- Deficit shifting left:
  - **merge (equality)**: from 8 -> 6, `capacity_hurdle = 2`, `capacity_max_target = 2`, merged.
  - **insert (hover/pass-over)**: from 9 -> 6, inserted.
  - **merge with capacity increase**: from 10 -> 6, packet capacity updates 2 -> 8, merged.
- Excess shifting right:
  - **insert with capacity increase**: from 14 -> 15, packet capacity updates 1 -> 5, inserted.
  - **merge with capacity increase**: from 12 -> 15, packet capacity updates 1 -> 6, merged.
  - **merge with capacity increase**: from 11 -> 15, packet capacity updates 5 -> 7, merged.
  - **insert with unchanged capacity** (pure hover): from 1 -> 6, packet capacity stays 7 -> 7, inserted.
  - **merge with capacity increase**: from 15 -> 6, packet capacity updates 6 -> 11, merged.

Convergence / end state (high-level):
- After the final BALANCE pass, the algorithm terminates (`done = True`) with a reduced configuration dominated by one EXCESS group followed by BALANCED groups, demonstrating that the example triggers all relevant merge and shift branches without instability.

This example is used as a regression/illustration case to ensure:
- all legal merge rules are exercised (including `B (+) B`, which was previously missing),
- all illegal merge rules are attempted and rejected in the expected situations,
- shift logic covers insert vs merge, and capacity equality and capacity updates, in both directions.

"""
    energy_excess_per_phase_initial  = [4, 3, 3, 2, 6, 3, 1, 2, 2, 5, 2, 7, 2, 1, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [4, 5, 3, 2, 6, 2, 2, 2, 3, 8, 3, 5, 1, 1, 1, 2, 1, 5]

    ctx = Context(energy_excess_per_phase_initial=energy_excess_per_phase_initial, energy_deficit_per_phase_initial=energy_deficit_per_phase_initial)
    run_mEfES(ctx)

if __name__ == '__main__':
    run_example()