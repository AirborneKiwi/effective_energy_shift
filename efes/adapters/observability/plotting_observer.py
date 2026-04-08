from __future__ import annotations

from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt

from ..scenarios.plotting import plot_energy_packets
from ...domain.models import EfesState


class PlottingObserver:
    """
    Observer that renders the EfES energy packets at each algorithm step.

    Typical usage:
    - show=False, save_frames=True  -> good for debugging / animation creation
    - show=True                     -> interactive inspection step by step
    """

    def __init__(
        self,
        efficiency_discharging: float,
        *,
        show: bool = False,
        save_frames: bool = False,
        output_dir: str | Path = "debug_energy_packets",
        add_collect_plot: bool = True,
        add_count_plot: bool = True,
        close_after_plot: bool = True,
        stop_condition: Callable[[str, object, object], bool] | None = None,
    ) -> None:
        self._efficiency_discharging = efficiency_discharging
        self._show = show
        self._save_frames = save_frames
        self._output_dir = Path(output_dir)
        self._add_collect_plot = add_collect_plot
        self._add_count_plot = add_count_plot
        self._close_after_plot = close_after_plot
        self._stop_condition = stop_condition
        self._frame_index = 0

        if self._save_frames:
            self._output_dir.mkdir(parents=True, exist_ok=True)

    def on_step(self, efes_state: EfesState) -> bool:
        # Nothing meaningful to plot before phases exist.
        if not isinstance(efes_state, EfesState):
            return False

        if efes_state.phases is None:
            return False

        fig, _ = plot_energy_packets(
            current_step=efes_state.step,
            phases=efes_state.phases,
            mask=efes_state.mask,
            efficiency_discharging=self._efficiency_discharging,
            add_collect_plot=self._add_collect_plot,
            add_count_plot=self._add_count_plot,
            show=self._show,
        )

        if self._save_frames:
            target = self._output_dir / f"{self._frame_index:03d}_{efes_state.step}.png"
            fig.savefig(target, dpi=150, bbox_inches="tight")

        self._frame_index += 1

        if self._close_after_plot and not self._show:
            plt.close(fig)

        if self._stop_condition is not None:
            return bool(self._stop_condition(efes_state))

        return False