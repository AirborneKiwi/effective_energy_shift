from __future__ import annotations

from efes_core.domain.enums import PacketType
from mefes.domain.models import MefesState
from mefes.adapters.observability.pretty_print import format_phase_table_console, _groups_ids

class ConsoleLoggingObserver:
    """
    Observer replacement for the old mefes_log_decorators table/group logging.

    This covers:
    - step-level table logs
    - iteration logs
    - phase-group summaries

    It intentionally does not try to replace every low-level lane mutation log.
    Those are better handled by optional debug decorators on services/models.
    """

    def __init__(self, enabled: bool = True, verbose_groups: bool = True) -> None:
        self.enabled = enabled
        self.verbose_groups = verbose_groups

    def _print(self, text: str) -> None:
        if self.enabled:
            print(text)

    def on_step(self, state: MefesState):
        if not isinstance(state, MefesState):
            return
        match state.step:
            case 'INITIALIZED':
                self.on_init(state)
            case 'BALANCE STARTED':
                self.on_balance_started(state)
            case 'BALANCE COMPLETED':
                self.on_balance_completed(state)
            case 'NEXT ITERATION':
                self.on_iteration_started(state)
            case 'MERGE STARTED':
                self.on_merge_started(state)
            case 'MERGE COMPLETED':
                self.on_merge_completed(state)
            case 'SHIFT STARTED':
                self.on_shift_started(state)
            case 'SHIFT COMPLETED':
                self.on_shift_completed(state)
            case 'RUN DONE':
                self.on_run_completed(state)

    def on_init(self, state: MefesState) -> None:
        self._print("=== INITIALIZED ===")
        self._print(format_phase_table_console(state))

    def on_iteration_started(self, state: MefesState) -> None:
        self._print(f"\n=== ITERATION {state.n_iterations} ===")

    def on_balance_started(self, state: MefesState) -> None:
        self._print("vvvvvvvvvvvvvvvvv BALANCE vvvvvvvvvvvvvvvvv")
        self._print(format_phase_table_console(state))

    def on_balance_completed(self, state: MefesState) -> None:
        self._print(format_phase_table_console(state))
        self._print("^^^^^^^^^^^^^^^^^^ BALANCE ^^^^^^^^^^^^^^^^^^")

    def on_merge_started(self, state: MefesState) -> None:
        self._print("vvvvvvvvvvvvvvvvv MERGE vvvvvvvvvvvvvvvvv")
        if self.verbose_groups:
            self._print(f"Before merge of groups: {_groups_ids(state)}")
        self._print(format_phase_table_console(state))

    def on_merge_completed(self, state: MefesState) -> None:
        if self.verbose_groups:
            self._print(f"After merge of groups: {_groups_ids(state)}")
        self._print(format_phase_table_console(state))
        self._print("^^^^^^^^^^^^^^^^^^ MERGE ^^^^^^^^^^^^^^^^^^")

    def on_shift_started(self, state: MefesState) -> None:
        self._print("vvvvvvvvvvvvvvvvv SHIFT vvvvvvvvvvvvvvvvv")
        self._print(format_phase_table_console(state))

    def on_shift_completed(self, state: MefesState) -> None:
        self._print(format_phase_table_console(state))
        self._print("^^^^^^^^^^^^^^^^^^ SHIFT ^^^^^^^^^^^^^^^^^^")

    def on_run_completed(self, state: MefesState) -> None:
        self._print("=== RUN COMPLETED ===")
        self._print(format_phase_table_console(state))
        self._print('Energy packets are:')
        eps = []
        for pp in state.phase_pairs:
            for ep in pp.energy_packets[PacketType.BALANCED]:
                eps.append((float(ep.capacity),float(ep.energy)))
        self._print(eps)