from __future__ import annotations

import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from matplotlib.collections import  PatchCollection
from matplotlib.patches import  Rectangle
import numpy as np

from efes_core.adapters.scenarios.plotting import _configure_style

_configure_style()

def plot_energy_packets(
    current_step,
    phases,
    mask,
    efficiency_discharging,
    add_collect_plot: bool = True,
    add_count_plot: bool = True,
    final_callback=None,
    show: bool = True,
):
    cols = 1
    if add_collect_plot:
        cols += 1
    if add_count_plot:
        cols += 1

    width_ratios = [2]
    if add_collect_plot:
        width_ratios.append(1)
    if add_count_plot:
        width_ratios.append(1)

    fig, axs = plt.subplots(1, cols, figsize=(15, 4), width_ratios=tuple(width_ratios), sharey=True)
    if cols == 1:
        axs = [axs]

    x = np.arange(len(phases))
    width = 0.25
    energy_packets_excess = []
    energy_packets_deficit = []
    energy_packets_deficit_covered = []

    linewidth_excess = []
    linewidth_deficit = []
    colors_excess = []
    colors_deficit = []
    colors_deficit_covered = []
    capacity_max = 0

    for n_phase, phase in enumerate(phases):
        energy_packets_excess.extend(
            [Rectangle(xy=(n_phase - width + 1, y), width=width, height=height) for (y, height) in zip(phase.starts_excess, phase.energy_excess)]
        )
        energy_packets_deficit.extend(
            [Rectangle(xy=(n_phase + 1, y), width=width, height=height) for (y, height) in zip(phase.starts_deficit, phase.energy_deficit)]
        )
        energy_packets_deficit_covered.extend(
            [Rectangle(xy=(n_phase, y), width=1, height=height) for (y, height, balanced) in zip(phase.starts_deficit, phase.energy_deficit, phase.deficit_balanced) if balanced]
        )

        linewidth_excess.extend([(3 if balanced else 1) for balanced in phase.excess_balanced])
        linewidth_deficit.extend([(3 if balanced else 1) for balanced in phase.deficit_balanced])
        colors_excess.extend(phase.excess_ids)
        colors = np.full(len(phase.deficit_balanced), -1)
        colors[phase.deficit_balanced] = phase.excess_ids[phase.excess_balanced]
        colors_deficit.extend(colors)
        colors_deficit_covered.extend(colors[phase.deficit_balanced])

        capacity_max = max(
            capacity_max,
            (phase.starts_excess + phase.energy_excess).max(),
            (phase.starts_deficit + phase.energy_deficit).max(),
        )

    norm = mpl.colors.Normalize(vmin=0, vmax=max(colors_excess) if len(colors_excess) else 0)
    m = cm.ScalarMappable(norm=norm, cmap=cm.nipy_spectral)

    pc_excess = PatchCollection(
        energy_packets_excess,
        edgecolor="black",
        linewidths=linewidth_excess,
        facecolors=[m.to_rgba(color_excess) for color_excess in colors_excess],
    )
    pc_deficit = PatchCollection(
        energy_packets_deficit,
        edgecolor="black",
        linewidths=linewidth_deficit,
        facecolors=[(m.to_rgba(color_deficit) if color_deficit >= 0 else "white") for color_deficit in colors_deficit],
    )
    pc_deficit_covered = PatchCollection(
        energy_packets_deficit_covered,
        edgecolor="black",
        linewidths=1,
        facecolors=[m.to_rgba(color_deficit) for color_deficit in colors_deficit_covered],
    )

    col = 0
    axs[col].add_collection(pc_excess)
    axs[col].add_collection(pc_deficit)
    axs[col].set(
        xlim=(0.5, x.max() + 1.5),
        ylim=(0, capacity_max * 1.1 if capacity_max else 1),
        ylabel="Capacity [Wh]",
        xlabel="Phase [1]",
        title=f"Energy packets after step {current_step}",
    )
    axs[col].grid()

    if add_collect_plot:
        col += 1
        axs[col].add_collection(pc_deficit_covered)
        axs[col].set(xlim=(0, x.max() + 1.5), xlabel="Phase [1]", title='"Collect" results')
        axs[col].grid()

    if add_count_plot:
        col += 1
        count_results = _compute_battery_arrays_from_phases(phases, efficiency_discharging)
        axs[col].step(count_results["effectiveness_local"], count_results["capacity"])
        axs[col].set(xlim=(0, x.max() + 1.5), xlabel="Local effectiveness_local [1]", title='"Count" results')
        axs[col].grid()

    fig.tight_layout()

    if final_callback is not None:
        fig, axs = final_callback(fig, axs)

    if show:
        plt.show()
    return fig, axs



def _compute_battery_arrays_from_phases(phases, efficiency_discharging: float):
    capacity_phases = []
    energy_additional_phases = []

    for phase in phases:
        capacity_phases.extend(phase.starts_deficit[phase.deficit_balanced])
        energy_additional_phases.extend(phase.energy_deficit[phase.deficit_balanced])

    capacity_phases = np.array(capacity_phases)
    energy_additional_phases = np.array(energy_additional_phases)

    capacity = np.unique(np.sort(np.array([capacity_phases, capacity_phases + energy_additional_phases]).flatten()))
    effectiveness_local = np.zeros(len(capacity))

    for phase in phases:
        for lower, upper in zip(
            phase.starts_deficit[phase.deficit_balanced],
            phase.starts_deficit[phase.deficit_balanced] + phase.energy_deficit[phase.deficit_balanced],
        ):
            effectiveness_local[(lower <= capacity) & (capacity < upper)] += 1

    delta_capacity = np.diff(capacity)
    delta_energy_additional = effectiveness_local[:-1] * delta_capacity
    energy_additional = efficiency_discharging * np.array([0, *delta_energy_additional.cumsum()])

    return {
        "capacity": capacity,
        "energy_additional": energy_additional,
        "effectiveness_local": effectiveness_local,
    }
