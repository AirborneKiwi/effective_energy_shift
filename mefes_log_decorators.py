from decorator_registry import register_before, register_after

from typing import Iterable
from collections import deque

ENABLED: bool = False
decorator_group = __file__
def _enabled() -> bool:
    return ENABLED

from mefes_dataclasses import Context, PhasePair, PhaseGroup, PacketType, EnergyPacket, EnergyPacketLane, ShiftInput


# --- table loggers ---

def register_table_logger(target, title: str):
    @register_before(target, group=decorator_group, enabled=_enabled)
    def _before(self, *a, **k):
        print(f"vvvvvvvvvvvvvvvvv {title} vvvvvvvvvvvvvvvvv")
        print(format_phase_table_console(self))

    @register_after(target, group=decorator_group, enabled=_enabled)
    def _after(self, _res, *a, **k):
        print(format_phase_table_console(self))
        print(f"^^^^^^^^^^^^^^^^^^ {title} ^^^^^^^^^^^^^^^^^^")


register_table_logger(Context.balance, "BALANCE")
register_table_logger(Context.merge, "MERGE")
register_table_logger(Context.shift, "SHIFT")


# --- group merge loggers ---

def _groups_ids(self) -> list[str]:
    return [pg.ID for pg in self.phase_groups]


@register_before(Context._stack_merge, group=decorator_group, enabled=_enabled)
def _stack_merge_before(self, *a, **k):
    print(f"Before merge of inner groups: {_groups_ids(self)}")


@register_after(Context._stack_merge, group=decorator_group, enabled=_enabled)
def _stack_merge_after(self, _res, *a, **k):
    print(f"After merge of inner groups: {_groups_ids(self)}")


@register_before(Context._boundary_merge, group=decorator_group, enabled=_enabled)
def _boundary_merge_before(self, *a, **k):
    print(f"Before merge of boundary groups: {_groups_ids(self)}")


@register_after(Context._boundary_merge, group=decorator_group, enabled=_enabled)
def _boundary_merge_after(self, _res, *a, **k):
    print(f"After merge of boundary groups: {_groups_ids(self)}")


# --- EnergyPacketLane loggers ---

@register_after(EnergyPacketLane.pop_left, group=decorator_group, enabled=_enabled)
def _pop_left_after(self, _res, *a, **k):
    print(f'[{self.ID}] First {self.lane_type.name} packet removed. New packet count is {len(self)}')


@register_after(EnergyPacketLane.pop_right, group=decorator_group, enabled=_enabled)
def _pop_right_after(self, _res, *a, **k):
    print(f'[{self.ID}] Last {self.lane_type.name} packet removed. New packet count is {len(self)}')


@register_before(EnergyPacketLane.append_packet, group=decorator_group, enabled=_enabled)
def _append_packet_before(self, energy_packet, *a, **k):
    print(f'[{self.ID}] Appending packet: {energy_packet}')


@register_before(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def _append_packet_left_before(self, energy_packet, *a, **k):
    print(f'[{self.ID}] Appending packet left: {energy_packet}')


@register_after(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def _append_packet_left_after(self, _res, energy_packet, *a, **k):
    print(f'[{self.ID}] Packet appended left. New packet count is {len(self)}')


@register_before(EnergyPacketLane.lift_front_to, group=decorator_group, enabled=_enabled)
def _lift_front_to_before(self, level, *a, **k):
    print(f'[{self.ID}] Lift request to {level}')


# --- PhasePair / PhaseGroup loggers ---

@register_before(PhasePair.balance_first_packet, group=decorator_group, enabled=_enabled)
def _balance_first_packet_before(self, *a, **k):
    energy_packet_exs = self.energy_packets[PacketType.EXCESS].peek_left()
    energy_packet_def = self.energy_packets[PacketType.DEFICIT].peek_left()
    print(f'[{self.ID}] Balancing EXCESS {energy_packet_exs} and DEFICIT {energy_packet_def}')
    if energy_packet_exs.energy > energy_packet_def.energy + 1e-8:
        print(f'[{self.ID}] EXCESS remaining')
    elif energy_packet_def.energy > energy_packet_exs.energy + 1e-8:
        print(f'[{self.ID}] DEFICIT remaining')


@register_before(PhaseGroup.balance, group=decorator_group, enabled=_enabled)
def _balance_group_before(self, *a, **k):
    if self.group_type == PacketType.BALANCED:
        print(f'[{self.ID}] Nothing to balance.')
    else:
        print(f'[{self.ID}] Balancing group: {self}')


@register_after(PhaseGroup.balance, group=decorator_group, enabled=_enabled)
def _balance_group_after(self, _res, *a, **k):
    print(f'[{self.ID}] Now: {self}')


@register_before(PhaseGroup.merge_with, group=decorator_group, enabled=_enabled)
def _merge_with_before(self, other, *a, **k):
    print(f'[{self.ID}] Merging with "{other.ID}"')


@register_after(PhaseGroup.merge_with, group=decorator_group, enabled=_enabled)
def _merge_with_after(self, res, other, *a, **k):
    merged, reason = res
    if not merged:
        print(f'[{self.ID}] Merge rejected with reason: {reason}')
    else:
        print(f'[{self.ID}] Merge allowed with reason: {reason}')
        print(f'[{self.ID}] Merged successfully. Right group can be removed.')


@register_before(PhaseGroup.shift, group=decorator_group, enabled=_enabled)
def _shift_before(self, ctx, *a, **k):
    if self.group_type == PacketType.BALANCED or (
        self.group_type == PacketType.DEFICIT and self.index_start == self.index_end
    ):
        print(f'[{self.ID}] Nothing to shift.')
    else:
        index_target = self.get_shift_target_index(ctx)
        print(f'[{self.ID}] Shifting energy packets to {index_target}.')


@register_before(PhaseGroup._apply_shift_input, group=decorator_group, enabled=_enabled)
def _apply_shift_input_before(self, phase_pair_target: PhasePair, capacity_hurdle: float, shift_input: ShiftInput, ctx, *a, **k):
    print(f'\n[{self.ID}] {shift_input}')
    if shift_input.index is None or shift_input.index == phase_pair_target.index_phase:
        print(f'[{self.ID}] No shift needed.')


@register_before(PhaseGroup._shift_all_from_to, group=decorator_group, enabled=_enabled)
def _shift_all_from_to_before(self, phase_pair_source, phase_pair_target, capacity_hurdle, *a, **k):
    print(f'[{self.ID}] Shift from {phase_pair_source.ID} to {phase_pair_target.ID}')


@register_before(PhaseGroup._shift_one_from_to, group=decorator_group, enabled=_enabled)
def _shift_one_from_to_before(self, phase_pair_source: PhasePair, phase_pair_target: PhasePair, capacity_hurdle, *a, **k):
    print(f'[{self.ID}] Shift needed for {phase_pair_source.n_packets[self.group_type]} packet(s).')
    energy_packet = phase_pair_source.energy_packets[self.group_type].peek_left()
    print(f'[{self.ID}] Shifting {energy_packet}')
    if energy_packet.starts_below_level(capacity_hurdle):
        print(f'[{self.ID}] Packet jumps over hurdle {capacity_hurdle} -> increase packets capacity')




""" - - - - - - PRETTY PRINT METHODS - - - - - -"""

def short_phases(ctx: Context) -> str:
    s = ''
    for pg in ctx.phase_groups:
        if pg.index_start == 0 or pg.index_start > pg.index_end:
            s += '|'
        s += pg.group_type.name[0]
    return s


PHASE_COL_TYPES = (PacketType.EXCESS, PacketType.BALANCED, PacketType.DEFICIT)

def _pp_get_energy_packets(pp: PhasePair, tp: PacketType):
    # Backward-compatible: missing BALANCED -> empty deque
    try:
        return pp.energy_packets[tp].dq
    except KeyError:
        return deque()


def _pp_get_n(pp: PhasePair, tp: PacketType) -> int:
    # Prefer new API
    if hasattr(pp, "n_packets"):
        return int(pp.n_packets[tp])
    # Fallback to old API
    if tp == PacketType.BALANCED:
        return 0
    return int(pp.n_packets.get[tp])


def _fmt_num(x: float) -> str:
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return f"{x:g}"


def _fmt_packet(energy_packet: EnergyPacket) -> str:
    return f"{_fmt_num(energy_packet.capacity)},{_fmt_num(energy_packet.energy)}"


def _iter_group_indices(index_start: int, index_end: int, n_phases: int) -> Iterable[int]:
    if index_end is None:
        index_end = index_start
    if index_start <= index_end:
        yield from range(index_start, index_end + 1)
    else:
        yield from range(index_start, n_phases)
        yield from range(0, index_end + 1)


def _group_marker(pg: PhaseGroup) -> str:
    return f'{pg.ID}'[3:]


def _build_phase_order_and_groups(ctx: Context) -> tuple[list[int], list[tuple[PhaseGroup, str, list[int]]]]:
    """
    Returns:
      - phase_order: flattened phase indices in current group order (deduped)
      - groups: list of (PhaseGroup, group_marker, indices_in_that_group_after_dedup)
    """
    n = ctx.N_phase_pairs
    seen: set[int] = set()

    phase_order: list[int] = []
    groups: list[tuple[PhaseGroup, str, list[int]]] = []

    for pg in ctx.phase_groups:
        raw = list(_iter_group_indices(pg.index_start, pg.index_end, n))
        kept: list[int] = []
        for i in raw:
            if i in seen:
                continue
            seen.add(i)
            kept.append(i)
            phase_order.append(i)
        if kept:
            groups.append((pg, _group_marker(pg), kept))

    return phase_order, groups


def format_phase_table_console(ctx: Context) -> str:
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
    n_row: list[str] = [str(_pp_get_n(ctx.phase_pairs[i], tp)) for (i, tp) in col_specs]

    # packet rows
    max_k = 0
    for i in phase_order:
        pp = ctx.phase_pairs[i]
        for tp in PHASE_COL_TYPES:
            max_k = max(max_k, len(_pp_get_energy_packets(pp, tp)))

    ep_rows: list[tuple[str, list[str]]] = []
    for k in range(max_k):
        row: list[str] = []
        for i, tp in col_specs:
            energy_packets = _pp_get_energy_packets(ctx.phase_pairs[i], tp)
            row.append(_fmt_packet(energy_packets[k]) if k < len(energy_packets) else "")
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
            pg: PhaseGroup,
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
                h_segments.append((_fmt_num(si.capacity_hurdle), w))
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
            h_segments.append((_fmt_num(si.capacity_hurdle), w))
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



