from __future__ import annotations

from mefes.domain.models import MefesState


def print_final_summary(state: MefesState) -> None:
    print()
    print("Final state:")
    print(f"done={state.done}")
    print(f"iterations={state.n_iterations}")
    print(f"n_phase_groups={state.n_phase_groups}")
    print(f"n_unbalanced_total={state.n_unbalanced_total}")
    print(f"n_unbalanced_excess={state.n_unbalanced_excess}")
    print(f"n_unbalanced_deficit={state.n_unbalanced_deficit}")