from decorator_registry import register_before, register_after
from typing import Callable
from dataclasses import dataclass

ENABLED: bool = False
decorator_group = __file__

def _enabled() -> bool:
    return ENABLED

from mefes_dataclasses import (
    Context, PhasePair, PhaseGroup, PacketType, EnergyPacket, EnergyPacketLane
)

_shift_ctx = []

@dataclass
class DecShiftCtx:
    packet_type: PacketType
    source_index: int = None
    target_index: int = None
    source_capacity: float = None
    target_capacity: float = None

    def as_tex_cmd(self):
        if self.packet_type == PacketType.EXCESS:
            return (
                r'\pgfplotExcessShift{'
                + str(self.source_index) + '}{' + str(self.source_capacity) + '}{'
                + str(self.target_index) + '}{' + str(self.target_capacity) + '};'
            )
        if self.packet_type == PacketType.DEFICIT:
            return (
                r'\pgfplotDeficitShift{'
                + str(self.source_index) + '}{' + str(self.source_capacity) + '}{'
                + str(self.target_index) + '}{' + str(self.target_capacity) + '};'
            )


# ---- PhaseGroup._shift_one_from_to ----

@register_before(PhaseGroup._shift_one_from_to, group=decorator_group, enabled=_enabled)
def tex_shift_one_from_to_before(
    self,
    phase_pair_source: PhasePair,
    phase_pair_target: PhasePair,
    capacity_hurdle: float,
    *a, **k
):
    ep_before = phase_pair_source.energy_packets[self.group_type].peek_left()
    _shift_ctx.append(DecShiftCtx(
        packet_type=self.group_type,
        source_index=phase_pair_source.index_phase,
        source_capacity=ep_before.capacity,
        target_index=phase_pair_target.index_phase,
    ))


@register_after(PhaseGroup._shift_one_from_to, group=decorator_group, enabled=_enabled)
def tex_shift_one_from_to_after(
    self,
    _res,
    phase_pair_source: PhasePair,
    phase_pair_target: PhasePair,
    capacity_hurdle: float,
    *a, **k
):
    ep_after = phase_pair_target.energy_packets[self.group_type].peek_right()
    _shift_ctx[-1].target_capacity = ep_after.capacity


# ---- Context.shift ----

@register_before(Context.shift, group=decorator_group, enabled=_enabled)
def tex_shift_groups_before(self, *a, **k):
    _shift_ctx.clear()


@register_after(Context.shift, group=decorator_group, enabled=_enabled)
def tex_shift_groups_after(self, _res, *a, **k):
    def add_content_func(lines):
        lines.extend([sc.as_tex_cmd() for sc in _shift_ctx])
        return lines

    create_pgf_snapshot(self, step='shift', add_content_func=add_content_func)
    _shift_ctx.clear()


# ---- Context.run_mEfES ----

@register_before(Context.run_mEfES, group=decorator_group, enabled=_enabled)
def tex_log_run_mEfES_before(self, *a, **k):
    create_pgf_snapshot(self, step='initialization', add_last_snapshot=False, clear_folder=True)


@register_after(Context.run_mEfES, group=decorator_group, enabled=_enabled)
def tex_log_run_mEfES_after(self, _res, *a, **k):
    create_pgf_snapshot(self, step='final', add_last_snapshot=False)


# ---- Context.merge ----

@register_after(Context.merge, group=decorator_group, enabled=_enabled)
def tex_merge_groups_after(self, _res, *a, **k):
    def add_content_func(lines):
        return lines
    create_pgf_snapshot(self, step='merge', add_content_func=add_content_func)


# ---- Context.balance ----

@register_after(Context.balance, group=decorator_group, enabled=_enabled)
def tex_log_balance_after(self, _res, *a, **k):
    def add_content_func(lines):
        return lines
    create_pgf_snapshot(self, step='balance', add_content_func=add_content_func)

def create_pgf_snapshot(ctx: Context, folder='./tex/fig_mEfES_example', clear_folder=False, step='', add_last_snapshot=True, add_content_func=None):
    if not hasattr(ctx, '_last_lines_axis_0_content'):
        setattr(ctx, '_last_lines_axis_0_content', None)

    lines = []

    if add_last_snapshot and ctx._last_lines_axis_0_content:
        lines.append(r'\begin{axis}[')
        lines.append(r'  mefes axis,')
        lines.append(r'  name=main plot,')
        lines.append(r'  ymajorgrids=true,')
        lines.append(r'  grid style=dashed,')
        lines.append(r'  clip=false,')
        lines.append(r'  opacity=0.2,')
        lines.append(r']')
        lines.extend(ctx._last_lines_axis_0_content)
        lines.append(r'\end{axis}')
        lines.append('')

    lines.append(r'\begin{axis}[')
    lines.append(r'  mefes axis,')
    lines.append(r'  name=main plot,')
    lines.append(r'  ymajorgrids=true,')
    lines.append(r'  grid style=dashed,')
    lines.append(r'  clip=false,')
    lines.append(r'  title={\textbf{' + step + r'}},')
    lines.append(r']')

    lines_axis_0_content = []
    for pp in ctx.phase_pairs:
        lines_axis_0_content.append(r'  % Phase pair ' + str(pp.index_phase))
        for ep in pp.energy_packets[PacketType.EXCESS]:
            lines_axis_0_content.append(r'\pgfplotExcessBar{}{' + str(pp.index_phase) +r'}{' + str(ep.capacity) +  r'}{' + str(ep.energy) + r'};')
        for ep in pp.energy_packets[PacketType.DEFICIT]:
            lines_axis_0_content.append(r'\pgfplotDeficitBar{}{' + str(pp.index_phase) + r'}{' + str(ep.capacity) + r'}{' + str(ep.energy) + r'};')
        for ep in pp.energy_packets[PacketType.BALANCED]:
            lines_axis_0_content.append(r'\pgfplotBalancedBar{}{' + str(pp.index_phase) +r'}{' + str(ep.capacity) +  r'}{' + str(ep.energy) + r'};')

    # for balance, we add the hurdles in BAL groups and redraw packets with a thick outline for the other cases
    for pg in ctx.phase_groups:
        hurdle_index_start = pg.index_start
        hurdle_index_end = None
        hurdle_capacity = 0
        hurdle_started = False

        for shift_input in pg.shift_inputs:
            if shift_input.index is None:
                # start detection of the hurdle index, by checking for the larges BAL phase pair
                hurdle_started = True
                hurdle_capacity = shift_input.capacity_hurdle

            if hurdle_started and shift_input.index is not None:
                hurdle_index_end = shift_input.index - 1
                lines_axis_0_content.append(r'\pgfplotHurdle{' + str(hurdle_index_start) + r'}{' + str(
                    hurdle_index_end) + r'}{' + str(hurdle_capacity) + r'}')
                hurdle_started = False

            if shift_input.index is not None:
                hurdle_index_start = shift_input.index + 1
                # redraw energy packets
                pp = ctx.phase_pairs[shift_input.index]
                for ep in pp.energy_packets[PacketType.EXCESS]:
                    lines_axis_0_content.append(r'\pgfplotExcessBar{very thick}{' + str(pp.index_phase) + r'}{' + str(
                        ep.capacity) + r'}{' + str(ep.energy) + r'};')
                for ep in pp.energy_packets[PacketType.DEFICIT]:
                    lines_axis_0_content.append(r'\pgfplotDeficitBar{very thick}{' + str(pp.index_phase) + r'}{' + str(
                        ep.capacity) + r'}{' + str(ep.energy) + r'};')

        if hurdle_started:
            hurdle_index_end = pg.index_end
            lines_axis_0_content.append(
                r'\pgfplotHurdle{' + str(hurdle_index_start) + r'}{' + str(hurdle_index_end) + r'}{' + str(
                    hurdle_capacity) + r'}')

    ctx._last_lines_axis_0_content = lines_axis_0_content

    lines.extend(lines_axis_0_content)
    if add_content_func:
        lines = add_content_func(lines)

    lines.append(r'\end{axis}')
    lines.append('')

    lines.append(r'\begin{axis}[')
    lines.append(r'  mefes axis,')
    lines.append(r'  yshift=-2.5\baselineskip,')
    lines.append(r'  height=0.2\linewidth,')
    lines.append(r'  ymin = -1, ymax = 1,')
    lines.append(r'  clip=false,')
    lines.append(r'  axis x line=none,')
    lines.append(r'  axis y line=none,')
    lines.append(r']')

    group_type_mapping = {
        PacketType.UNDEFINED: r'$\undefinedGroupSymbol$',
        PacketType.EXCESS: r'$\excessGroupSymbol$',
        PacketType.DEFICIT: r'$\deficitGroupSymbol$',
        PacketType.BALANCED: r'$\balancedGroupSymbol$',
    }
    for pg in ctx.phase_groups:
        if pg.index_start <= pg.index_end:
            lines.append(r'  \pgfplotNormalPhaseGroup{'+ group_type_mapping[pg.group_type] + r'}{' + str(pg.index_start) + r'}{' + str(pg.index_end) + r'};')
        else:
            lines.append(r'  \pgfplotWrappingPhaseGroup{'+ group_type_mapping[pg.group_type] + r'}{}{' + str(pg.index_start) + r'}{' + str(pg.index_end) + r'}')

    lines.append(r'\end{axis}')
    s = '\n'.join(lines)

    filename = f'fig_mEfES_example_it_{ctx.n_iterations}'
    if step:
        filename += f'_{step}'
    filename += '.tex'

    from pathlib import Path
    folder = Path(folder)
    if clear_folder:

        def rm_tree(pth: Path):
            if not pth.exists():
                return
            for child in pth.iterdir():
                if child.is_file():
                    child.unlink()
                else:
                    rm_tree(child)
            pth.rmdir()

        rm_tree(folder)

    folder.mkdir(parents=True, exist_ok=True)
    file_path: Path = folder / filename
    file_path.write_text(s)
    return s

