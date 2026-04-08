from __future__ import annotations

from collections import deque
from typing import Iterable

from efes_core.domain.enums import PacketType
from mefes.domain.models import EnergyPacket, MefesState, PhaseGroup, PhasePair

def short_phases(state: MefesState) -> str:
    s = ""
    for pg in state.phase_groups:
        if pg.index_start == 0 or pg.index_start > pg.index_end:
            s += "|"
        s += pg.group_type.name[0]
    return s


PHASE_COL_TYPES = (PacketType.EXCESS, PacketType.BALANCED, PacketType.DEFICIT)

def _pp_get_energy_packets(pp: PhasePair, tp: PacketType):
    try:
        return pp.energy_packets[tp].dq
    except KeyError:
        return deque()


def _pp_get_n(pp: PhasePair, tp: PacketType) -> int:
    return int(pp.n_packets[tp])


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
    return f"{pg.id}"[3:]


def _build_phase_order_and_groups(
    state: MefesState,
) -> tuple[list[int], list[tuple[PhaseGroup, str, list[int]]]]:
    n = state.n_phase_pairs
    seen: set[int] = set()

    phase_order: list[int] = []
    groups: list[tuple[PhaseGroup, str, list[int]]] = []

    for pg in state.phase_groups:
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


def format_phase_table_console(state: MefesState) -> str:
    phase_order, groups = _build_phase_order_and_groups(state)
    n_types = len(PHASE_COL_TYPES)

    col_specs: list[tuple[int, PacketType]] = []
    for i in phase_order:
        for tp in PHASE_COL_TYPES:
            col_specs.append((i, tp))

    boundary_after_col: set[int] = set()
    col_cursor = 0
    for _pg, _marker, idxs in groups:
        span = n_types * len(idxs)
        boundary_after_col.add(col_cursor + span - 1)
        col_cursor += span

    boundary_after_phase_seg: set[int] = set()
    phase_cursor = 0
    for _pg, _marker, idxs in groups:
        boundary_after_phase_seg.add(phase_cursor + len(idxs) - 1)
        phase_cursor += len(idxs)

    type_map = {
        PacketType.EXCESS: "e",
        PacketType.DEFICIT: "d",
        PacketType.BALANCED: "b",
    }
    type_row: list[str] = [type_map[tp] for (_i, tp) in col_specs]
    n_row: list[str] = [str(_pp_get_n(state.phase_pairs[i], tp)) for (i, tp) in col_specs]

    max_k = 0
    for i in phase_order:
        pp = state.phase_pairs[i]
        for tp in PHASE_COL_TYPES:
            max_k = max(max_k, len(_pp_get_energy_packets(pp, tp)))

    ep_rows: list[tuple[str, list[str]]] = []
    for k in range(max_k):
        row: list[str] = []
        for i, tp in col_specs:
            energy_packets = _pp_get_energy_packets(state.phase_pairs[i], tp)
            row.append(_fmt_packet(energy_packets[k]) if k < len(energy_packets) else "")
        ep_rows.append((f"ep[{k}]", row))

    base_rows_for_widths: list[list[str]] = [type_row, n_row] + [r for _, r in ep_rows]
    col_ws = [max((len(r[c]) for r in base_rows_for_widths), default=0) for c in range(len(col_specs))]
    label_w = max(len("n"), *(len(lbl) for lbl, _ in ep_rows), 0)

    def _span_width(c0: int, span_cols: int) -> int:
        return sum(col_ws[c0:c0 + span_cols]) + 3 * (span_cols - 1)

    def _cell(text: str, width: int) -> str:
        return f"{text:^{width}}"

    def _render_segments(
        label: str,
        segments: list[tuple[str, int]],
        thick_after_seg: set[int] | None = None,
    ) -> str:
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

    group_segments: list[tuple[str, int]] = []
    c = 0
    for _pg, marker, idxs in groups:
        span = n_types * len(idxs)
        group_segments.append((marker, _span_width(c, span)))
        c += span
    thick_after_group_seg = set(range(len(group_segments) - 1))

    index_segments: list[tuple[str, int]] = []
    c = 0
    for i in phase_order:
        index_segments.append((str(i), _span_width(c, n_types)))
        c += n_types

    def _build_shift_segments_for_group(
        pg: PhaseGroup,
        idxs: list[int],
        c0_group: int,
    ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        pos_map: dict[int, int] = {ix: p for p, ix in enumerate(idxs)}
        sis = list(pg.shift_inputs) if getattr(pg, "shift_inputs", None) else []

        next_non_none_pos: list[int | None] = [None] * len(sis)
        nxt: int | None = None
        for j in range(len(sis) - 1, -1, -1):
            next_non_none_pos[j] = nxt
            si = sis[j]
            if si.index is not None and si.index in pos_map:
                nxt = pos_map[si.index]

        h_segments: list[tuple[str, int]] = []
        si_segments: list[tuple[str, int]] = []

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

            if si.index not in pos_map:
                continue

            pos = pos_map[si.index]
            if pos > p:
                span_phases = pos - p
                w = _span_width(c0_group + p * n_types, span_phases * n_types)
                h_segments.append(("", w))
                si_segments.append(("", w))
                p = pos

            if pos < p:
                continue

            w = _span_width(c0_group + p * n_types, n_types)
            h_segments.append((_fmt_num(si.capacity_hurdle), w))
            si_segments.append((str(si.index), w))
            p += 1

        if p < len(idxs):
            span_phases = len(idxs) - p
            w = _span_width(c0_group + p * n_types, span_phases * n_types)
            h_segments.append(("", w))
            si_segments.append(("", w))

        if not h_segments:
            w = _span_width(c0_group, len(idxs) * n_types)
            h_segments = [("", w)]
            si_segments = [("", w)]

        return h_segments, si_segments

    h_segments_all: list[tuple[str, int]] = []
    si_segments_all: list[tuple[str, int]] = []
    thick_after_shift_seg: set[int] = set()

    c0 = 0
    for gi, (pg, _marker, idxs) in enumerate(groups):
        h_segs, si_segs = _build_shift_segments_for_group(pg, idxs, c0)
        h_segments_all.extend(h_segs)
        si_segments_all.extend(si_segs)

        if gi != len(groups) - 1:
            thick_after_shift_seg.add(len(h_segments_all) - 1)

        c0 += n_types * len(idxs)

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


def _groups_ids(state: MefesState) -> list[str]:
    return [pg.id for pg in state.phase_groups]