from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from decorator_registry import register_after, register_before

from efes_core.domain.enums import PacketType
from ..application.use_cases import MefesImplementation
from ..domain.models import MefesState, PhasePair
from ..domain.services import PhaseGroupService

ENABLED: bool = False
decorator_group = __file__
targets = [PhaseGroupService, MefesImplementation]

def _enabled() -> bool:
    return ENABLED


_shift_ctx: list["DecShiftCtx"] = []


@dataclass
class DecShiftCtx:
    packet_type: PacketType
    source_index: int | None = None
    target_index: int | None = None
    source_capacity: float | None = None
    target_capacity: float | None = None

    def as_tex_cmd(self) -> str:
        if self.packet_type == PacketType.EXCESS:
            return (
                r"\pgfplotExcessShift{"
                + str(self.source_index) + "}{" + str(self.source_capacity) + "}{"
                + str(self.target_index) + "}{" + str(self.target_capacity) + "};"
            )
        if self.packet_type == PacketType.DEFICIT:
            return (
                r"\pgfplotDeficitShift{"
                + str(self.source_index) + "}{" + str(self.source_capacity) + "}{"
                + str(self.target_index) + "}{" + str(self.target_capacity) + "};"
            )
        return ""


# ------------------------------------------------------------
# PhaseGroupService._shift_one_from_to
# ------------------------------------------------------------

@register_before(PhaseGroupService._shift_one_from_to, group=decorator_group, enabled=_enabled)
def tex_shift_one_from_to_before(
    packet_type: PacketType,
    phase_pair_source: PhasePair,
    phase_pair_target: PhasePair,
    capacity_hurdle: float,
):
    ep_before = phase_pair_source.energy_packets[packet_type].peek_left()
    if ep_before is None:
        return

    _shift_ctx.append(
        DecShiftCtx(
            packet_type=packet_type,
            source_index=phase_pair_source.index_phase,
            source_capacity=ep_before.capacity,
            target_index=phase_pair_target.index_phase,
        )
    )


@register_after(PhaseGroupService._shift_one_from_to, group=decorator_group, enabled=_enabled)
def tex_shift_one_from_to_after(
    _res,
    packet_type: PacketType,
    phase_pair_source: PhasePair,
    phase_pair_target: PhasePair,
    capacity_hurdle: float,
):
    if not _shift_ctx:
        return

    ep_after = phase_pair_target.energy_packets[packet_type].peek_right()
    if ep_after is None:
        return

    _shift_ctx[-1].target_capacity = ep_after.capacity


# ------------------------------------------------------------
# MefesImplementation._shift
# ------------------------------------------------------------

@register_before(MefesImplementation._shift, group=decorator_group, enabled=_enabled)
def tex_shift_groups_before(self: MefesImplementation):
    _shift_ctx.clear()


@register_after(MefesImplementation._shift, group=decorator_group, enabled=_enabled)
def tex_shift_groups_after(res, self: MefesImplementation):
    def add_content_func(lines: list[str]) -> list[str]:
        lines.extend([sc.as_tex_cmd() for sc in _shift_ctx if sc.as_tex_cmd()])
        return lines

    create_pgf_snapshot(self.state, step="shift", add_content_func=add_content_func)
    _shift_ctx.clear()


# ------------------------------------------------------------
# MefesImplementation.execute
# ------------------------------------------------------------

@register_before(MefesImplementation.execute, group=decorator_group, enabled=_enabled)
def tex_log_run_mefes_before(self: MefesImplementation):
    create_pgf_snapshot(
        self.state,
        step="initialization",
        add_last_snapshot=False,
        clear_folder=True,
    )


@register_after(MefesImplementation.execute, group=decorator_group, enabled=_enabled)
def tex_log_run_mefes_after(res, self: MefesImplementation):
    create_pgf_snapshot(self.state, step="final", add_last_snapshot=False)


# ------------------------------------------------------------
# MefesImplementation._merge
# ------------------------------------------------------------

@register_after(MefesImplementation._merge, group=decorator_group, enabled=_enabled)
def tex_merge_groups_after(res, self: MefesImplementation):
    create_pgf_snapshot(self.state, step="merge", add_content_func=lambda lines: lines)


# ------------------------------------------------------------
# MefesImplementation._balance
# ------------------------------------------------------------

@register_after(MefesImplementation._balance, group=decorator_group, enabled=_enabled)
def tex_log_balance_after(res, self: MefesImplementation):
    create_pgf_snapshot(self.state, step="balance", add_content_func=lambda lines: lines)


def create_pgf_snapshot(
    state: MefesState,
    folder: str = "./tex/fig_mEfES_example",
    clear_folder: bool = False,
    step: str = "",
    add_last_snapshot: bool = True,
    add_content_func: Callable[[list[str]], list[str]] | None = None,
) -> str:
    if not hasattr(state, "_last_lines_axis_0_content"):
        setattr(state, "_last_lines_axis_0_content", None)

    lines: list[str] = []

    if add_last_snapshot and state._last_lines_axis_0_content:
        lines.append(r"\begin{axis}[")
        lines.append(r"  mefes axis,")
        lines.append(r"  name=main plot,")
        lines.append(r"  ymajorgrids=true,")
        lines.append(r"  grid style=dashed,")
        lines.append(r"  clip=false,")
        lines.append(r"  opacity=0.2,")
        lines.append(r"]")
        lines.extend(state._last_lines_axis_0_content)
        lines.append(r"\end{axis}")
        lines.append("")

    lines.append(r"\begin{axis}[")
    lines.append(r"  mefes axis,")
    lines.append(r"  name=main plot,")
    lines.append(r"  ymajorgrids=true,")
    lines.append(r"  grid style=dashed,")
    lines.append(r"  clip=false,")
    lines.append(r"  title={\textbf{" + step + r"}},")
    lines.append(r"]")

    lines_axis_0_content: list[str] = []
    for pp in state.phase_pairs:
        lines_axis_0_content.append(r"  % Phase pair " + str(pp.index_phase))
        for ep in pp.energy_packets[PacketType.EXCESS]:
            lines_axis_0_content.append(
                r"\pgfplotExcessBar{}{" + str(pp.index_phase) + r"}{" + str(ep.capacity) + r"}{" + str(ep.energy) + r"};"
            )
        for ep in pp.energy_packets[PacketType.DEFICIT]:
            lines_axis_0_content.append(
                r"\pgfplotDeficitBar{}{" + str(pp.index_phase) + r"}{" + str(ep.capacity) + r"}{" + str(ep.energy) + r"};"
            )
        for ep in pp.energy_packets[PacketType.BALANCED]:
            lines_axis_0_content.append(
                r"\pgfplotBalancedBar{}{" + str(pp.index_phase) + r"}{" + str(ep.capacity) + r"}{" + str(ep.energy) + r"};"
            )

    for pg in state.phase_groups:
        hurdle_index_start = pg.index_start
        hurdle_index_end = None
        hurdle_capacity = 0.0
        hurdle_started = False

        for shift_input in pg.shift_inputs:
            if shift_input.index is None:
                hurdle_started = True
                hurdle_capacity = shift_input.capacity_hurdle

            if hurdle_started and shift_input.index is not None:
                hurdle_index_end = shift_input.index - 1
                lines_axis_0_content.append(
                    r"\pgfplotHurdle{"
                    + str(hurdle_index_start) + r"}{"
                    + str(hurdle_index_end) + r"}{"
                    + str(hurdle_capacity) + r"}"
                )
                hurdle_started = False

            if shift_input.index is not None:
                hurdle_index_start = shift_input.index + 1
                pp = state.phase_pairs[shift_input.index]
                for ep in pp.energy_packets[PacketType.EXCESS]:
                    lines_axis_0_content.append(
                        r"\pgfplotExcessBar{very thick}{"
                        + str(pp.index_phase) + r"}{"
                        + str(ep.capacity) + r"}{"
                        + str(ep.energy) + r"};"
                    )
                for ep in pp.energy_packets[PacketType.DEFICIT]:
                    lines_axis_0_content.append(
                        r"\pgfplotDeficitBar{very thick}{"
                        + str(pp.index_phase) + r"}{"
                        + str(ep.capacity) + r"}{"
                        + str(ep.energy) + r"};"
                    )

        if hurdle_started:
            hurdle_index_end = pg.index_end
            lines_axis_0_content.append(
                r"\pgfplotHurdle{"
                + str(hurdle_index_start) + r"}{"
                + str(hurdle_index_end) + r"}{"
                + str(hurdle_capacity) + r"}"
            )

    state._last_lines_axis_0_content = lines_axis_0_content

    lines.extend(lines_axis_0_content)
    if add_content_func:
        lines = add_content_func(lines)

    lines.append(r"\end{axis}")
    lines.append("")

    lines.append(r"\begin{axis}[")
    lines.append(r"  mefes axis,")
    lines.append(r"  yshift=-2.5\baselineskip,")
    lines.append(r"  height=0.2\linewidth,")
    lines.append(r"  ymin = -1, ymax = 1,")
    lines.append(r"  clip=false,")
    lines.append(r"  axis x line=none,")
    lines.append(r"  axis y line=none,")
    lines.append(r"]")

    group_type_mapping = {
        PacketType.UNDEFINED: r"$\undefinedGroupSymbol$",
        PacketType.EXCESS: r"$\excessGroupSymbol$",
        PacketType.DEFICIT: r"$\deficitGroupSymbol$",
        PacketType.BALANCED: r"$\balancedGroupSymbol$",
    }

    for pg in state.phase_groups:
        if pg.index_start <= pg.index_end:
            lines.append(
                r"  \pgfplotNormalPhaseGroup{"
                + group_type_mapping[pg.group_type] + r"}{"
                + str(pg.index_start) + r"}{"
                + str(pg.index_end) + r"};"
            )
        else:
            lines.append(
                r"  \pgfplotWrappingPhaseGroup{"
                + group_type_mapping[pg.group_type] + r"}{}{"
                + str(pg.index_start) + r"}{"
                + str(pg.index_end) + r"}"
            )

    lines.append(r"\end{axis}")
    s = "\n".join(lines)

    filename = f"fig_mEfES_example_it_{state.n_iterations}"
    if step:
        filename += f"_{step}"
    filename += ".tex"

    folder_path = Path(folder)
    if clear_folder:
        _rm_tree(folder_path)

    folder_path.mkdir(parents=True, exist_ok=True)
    file_path = folder_path / filename
    file_path.write_text(s)
    return s


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_file():
            child.unlink()
        else:
            _rm_tree(child)
    path.rmdir()
    