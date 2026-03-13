from __future__ import annotations

from collections import deque
from typing import Deque, List, Tuple


# Import and register all decorators
import decorator_registry as dec_reg
import mefes_event_decorators as evt_dec
import mefes_tex_decorators as tex_dec
import mefes_log_decorators as log_dec
import mefes_test_decorators as test_dec

# Enable decorators as needed
DECORATOR_REGISTRIES = {
    'DEBUG_LOG': (log_dec, True),
    'REC_EVTS': (evt_dec, True),
    'TEX_LOG': (tex_dec, True),
    'CHECK_INVARIANTS': (test_dec, True),
}

for flag, (dec_module, enabled) in DECORATOR_REGISTRIES.items():
    dec_module.ENABLED = enabled
    if enabled:
        dec_reg.enable_group(dec_module.decorator_group)  # now they will be applied
    else:
        dec_reg.disable_group(dec_module.decorator_group)      # nothing from that group is applied


# Apply all enabled decorators for the module (all classes, methods, and functions) mefes_dataclasses
import mefes_dataclasses
dec_reg.apply_decorators(mefes_dataclasses)


from mefes_dataclasses import Context, EnergyPacketLane, PacketType, PhasePair, EnergyPacket, PhaseGroup

def run_example():
    """
This example is built to exercise the relevant corner-cases for the algorithm’s
**BALANCE -> MERGE -> SHIFT** pipeline on a *cyclic* phase sequence (wrap-around at N−1 -> 0).

-------------------------------------------------------------------------------
Concrete input used in this regression / illustration run
-------------------------------------------------------------------------------

Initial energies per phase (capacity-0 packets):

    energy_excess_per_phase_initial  = [40, 3, 10, 20, 60, 3, 1, 10, 2, 5, 2, 7, 2, 50, 2, 1, 4, 8]
    energy_deficit_per_phase_initial = [40, 5, 10, 20, 60, 2, 2, 10, 3, 8, 3, 5, 1, 50, 1, 2, 1, 5]

Each phase index `k` is represented as a **PhasePair** consisting of up to three packet lanes:
- `e` (excess packets)
- `b` (balanced packets)
- `d` (deficit packets)

Initially, each PhasePair contains exactly one excess packet and one deficit packet at capacity 0,
with energies taken from the arrays above.

-------------------------------------------------------------------------------
BALANCE (PhasePair classification + packet splitting)
-------------------------------------------------------------------------------

During **BALANCE**, each PhasePair is converted from type `UND` (undefined) into one of:
- `BAL` (balanced)  if excess == deficit (no split required),
- `EXC` (excess)    if excess > deficit  (split the excess packet at `capacity = deficit`),
- `DEF` (deficit)   if deficit > excess  (split the deficit packet at `capacity = excess`).

After BALANCE, each PhaseGroup stores a `shift_inputs` list. Each element is:

    ShiftInput(index: Optional[int], capacity_hurdle: int)

Interpretation (as printed in the tables):
- Row **SI** prints `shift_input.index` per PhasePair position.
  `None` denotes the PhasePair that anchors the *hurdle update only* (no direct shift).
- Row **H** prints the corresponding `capacity_hurdle`.

In the initial BALANCE of this run, every PhasePair becomes its own PhaseGroup, producing:
    types: "BDBBBEDBDDDEEBEDEE"
(i.e., BAL/DEF/EXC pattern over indices 0..17).

-------------------------------------------------------------------------------
MERGE (non-commutative group algebra, preserving shift direction)
-------------------------------------------------------------------------------

MERGE collapses adjacent PhaseGroups using the directed merge rules. The operation is not
commutative because it must preserve the direction of the later SHIFT.

Allowed merges (as observed in this run):
- Same-type merges:
  - `BAL (+) BAL`, `DEF (+) DEF`, `EXC (+) EXC`
- Direction-preserving merges:
  - `BAL (+) DEF`  (reason: "DEFICIT will be shifted left over BALANCE.")
  - `EXC (+) BAL`  (reason: "EXCESS will be shifted right over BALANCE.")

Not allowed (must be resolved by shifting first or by balancing):
- Any merge involving `UND`
- `BAL (+) EXC` or `DEF (+) BAL` (would lose directional intent)
- `EXC (+) DEF` / `DEF (+) EXC` (direct conflict)

In this run, MERGE demonstrates:
- a cycle-boundary `BAL (+) DEF` merge at indices 0 and 1 -> `0..1 DEF`
- repeated `BAL (+) BAL` merges at 2,3,4 -> `2..4 BAL`
- a long `DEF` chain collapsing to `6..10 DEF`
- adjacent `EXC` merges (`11..12`, `16..17`) and `EXC (+) BAL` absorption at `11..12 (+) 13`
- after later iterations, a wrap-around merge of two `EXC` blocks triggers a *rotation*:
  the log prints `Merged (wrap): Same type` followed by `Rotating phase groups by -2`.

-------------------------------------------------------------------------------
SHIFT (executing ShiftInputs; hurdle updates + conditional capacity lifting)
-------------------------------------------------------------------------------

SHIFT moves packets between PhasePairs inside a merged PhaseGroup, toward a target PhasePair
chosen by the group’s shift direction:

- `DEF` groups shift packets **left** (toward the group’s `index_start`)
- `EXC` groups shift packets **right** (toward the group’s `index_end`)
- `BAL` groups do not shift

SHIFT proceeds by iterating the group’s `ShiftInput` list in order. The log distinguishes:
1) **Hurdle update only** (`ShiftInput(index=None, capacity_hurdle=H)`):
   - Updates the active hurdle to `H`
   - Prints `No shift needed.`
2) **Shift step** (`ShiftInput(index=i, capacity_hurdle=H)`):
   - Prints `Shift from i to target`
   - Removes the top packet from lane `e` or `d` (depending on group type)
   - Attempts to append it at the target.

A key corner-case illustrated by the log:
- If the moved packet’s capacity is below the current hurdle, the log prints:
      `Packet jumped over hurdle X -> increase packets capacity`
  and the packet’s capacity is raised to the hurdle before insertion/merge at the target.

The *append* itself can either:
- append as a new packet (`Packet appended.`), or
- merge energy into an existing top packet at the same lane
  (log lines like `... top at <cap> was higher -> packets energy merged instead`).

This run demonstrates all of the following SHIFT behaviors:
- **Wrap-around shifting** across the cyclic boundary:
  EXC group `16..17` shifts from 17 -> 0 and then 16 -> 0.
- **Hurdle update without shifting** via `index=None` ShiftInputs:
  e.g. `ShiftInput(index=None, capacity_hurdle=40)` inside `0..1 DEF`,
  and `ShiftInput(index=None, capacity_hurdle=50)` inside `11..14 EXC`.
- **Capacity lifting due to hurdle jumps**:
  multiple occurrences of `Packet jumped over hurdle ... -> increase packets capacity`
  (e.g. 3->40, 2->10, 1->50, etc.).
- **Energy merges during append** when the destination already has a higher top capacity.

-------------------------------------------------------------------------------
Convergence and end state (what this log actually ends with)
-------------------------------------------------------------------------------

The log shows **two full iterations** after the initial pass:
- After the first SHIFT, some groups become `UND` again and must be re-balanced.
- Iteration 1 BALANCE produces a reduced set of groups, then MERGE collapses them further,
  including a wrap-around EXC merge that triggers group rotation.
- Iteration 2 BALANCE converts the remaining `UND` group `6..10` into `EXC` with
  `ShiftInput(index=6, capacity_hurdle=51)`, and the run terminates with:
      `self.done = True`

So, this input is a regression/illustration case to ensure:
- table output includes the additional **H** and **SI** rows reflecting `shift_inputs`,
- MERGE exercises both same-type merges and directional merges (`EXC (+) BAL`, `BAL (+) DEF`),
  including a **wrap-around** merge that requires rotating the group order,
- SHIFT demonstrates:
  - hurdle-only updates (`index=None`),
  - capacity lifting when jumping over the hurdle,
  - insertion vs. energy-merge effects at the destination,
  - cyclic boundary behavior.

The end result will be:
- a configuration dominated by BALANCED groups plus one EXCESS group (`6..10 EXC`),
  with the final hurdle recorded as `51` at shift index `6`.

The end result will be:
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            16..5 BAL                                                            ||                                        6..11 EXC                                        ||                       12..15 BAL                       |
H     |                                                                                                                                 ||        0        |                                                                       ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                                       ||                                                        |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     16      |     17      |     18      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8       |      9      |     10      |     11      ||     12      |     13      |      14      |     15      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,4 |   |   | 0,11 |   |   | 0,1 |   |   | 0,20 |   |   | 0,30 |   |   | 0,40 |   |   | 0,3 |   || 71,2 | 0,1  |   |   | 0,50 |   |   | 0,60 |   |   | 0,1 |   |   | 0,5 |   |   | 0,3 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,70 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 3,1  |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 60,2 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 70,1 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    energy_excess_per_phase_initial = [8, 1, 2, 10, 4, 4, 1, 5, 6, 1, 5, 3, 7, 2, 7, 2, 1, 3, 5]
    energy_deficit_per_phase_initial = [8, 2, 2, 10, 4, 3, 2, 5, 6, 2, 6, 4, 5, 1, 7, 1, 2, 1, 4]

    #energy_excess_per_phase_initial = [2,5,10,2,5]
    #energy_deficit_per_phase_initial = [1,10,3,10,1]

    result_ref = """
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PG    |                                                            16..5 BAL                                                            ||                                        6..11 EXC                                        ||                       12..15 BAL                       |
H     |                                                                                                                                 ||        0        |                                                                       ||                                                        |
SI    |                                                                                                                                 ||        6        |                                                                       ||                                                        |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PP    |     16      |     17      |     18      |      0       |      1      |      2       |      3       |      4       |      5      ||        6        |      7       |      8       |      9      |     10      |     11      ||     12      |     13      |      14      |     15      |
PT    | e |  b  | d | e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d | e |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d ||  e   |  b   | d | e |  b   | d | e |  b   | d | e |  b  | d | e |  b  | d | e |  b  | d || e |  b  | d | e |  b  | d | e |  b   | d | e |  b  | d |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
n     | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 ||  1   |  4   | 0 | 0 |  1   | 0 | 0 |  1   | 0 | 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1  | 0 || 0 |  1  | 0 | 0 |  1  | 0 | 0 |  1   | 0 | 0 |  1  | 0 |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ep[0] |   | 0,2 |   |   | 0,1 |   |   | 0,4 |   |   | 0,11 |   |   | 0,1 |   |   | 0,20 |   |   | 0,30 |   |   | 0,40 |   |   | 0,3 |   || 71,2 | 0,1  |   |   | 0,50 |   |   | 0,60 |   |   | 0,1 |   |   | 0,5 |   |   | 0,3 |   ||   | 0,5 |   |   | 0,1 |   |   | 0,70 |   |   | 0,1 |   |
ep[1] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 3,1  |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[2] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 60,2 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
ep[3] |   |     |   |   |     |   |   |     |   |   |      |   |   |     |   |   |      |   |   |      |   |   |      |   |   |     |   ||      | 70,1 |   |   |      |   |   |      |   |   |     |   |   |     |   |   |     |   ||   |     |   |   |     |   |   |      |   |   |     |   |
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

    ctx = Context(energy_excess_per_phase_initial=energy_excess_per_phase_initial, energy_deficit_per_phase_initial=energy_deficit_per_phase_initial)

    ctx.run_mEfES()


    result = log_dec.format_phase_table_console(ctx)
    if ('\n' + result + '\n') == result_ref:
        print('Result matches the reference :-)')
    else:
        print('The result differs from the reference :-(')
        print('Reference:\n', result_ref)

        print('Result:\n', result)

def build_worst_case_cycle(
    n_phases: int,
    *,
    base: int = 100,
    e_low: int = 2,
    e_high: int = 3
) -> Tuple[List[int], List[int]]:
    """
    Deterministic “anti-merge + slow-progress” initializer that enforces the type dynamics:

      Initial (after first BALANCE):  E D B E D B ...  (period 3)
      After SHIFT (only E shifts right): B U B B U B ... (period 3)
      After next BALANCE:               B D B B E B ... (U resolves alternating D/E)
      After MERGE:                      ... collapses to repeating (D,B,E) which is a rotation of (E,D,B),
                                       i.e. again non-mergeable at the group-type level.

    Construction idea (all energies strictly > 0):
      - Pick a large base A=base.
      - For E phases: (excess, deficit) = (A + e_k, A)   => residual excess = e_k
      - For D phases: (excess, deficit) = (A, A + d_k)   => residual deficit = d_k
      - For B phases: (excess, deficit) = (A, A)         => balanced

    After SHIFT, each D-phase receives the residual excess from its left-neighbor E-phase.
    That makes the D-phase UNDEFINED (U) and it will resolve to:
      - D if d_k > e_left
      - E if d_k < e_left

    We enforce an alternating resolution around the ring by choosing:
      for D_k at phase i (i%3==1):
        if k even:  d_k = e_left + 1  (forces D)
        if k odd:   d_k = max(1, e_left - 1) (forces E)

    Constraints:
      - n_phases must be a multiple of 3 to realize a perfect EDB tiling.
      - base, e_low, e_high must be positive integers.

    Returns:
      (energy_excess_per_phase_initial, energy_deficit_per_phase_initial)
    """
    n_phases = int(n_phases / 3) * 3

    if base <= 0 or e_low <= 0 or e_high <= 0:
        raise ValueError("base, e_low, e_high must be positive integers.")

    ex: List[int] = [0] * n_phases
    de: List[int] = [0] * n_phases

    # Choose residuals on E phases in a simple repeating 2-level pattern.
    # You can also just set e_low == e_high to make all E residuals equal.
    e_residuals: List[int] = []
    for k in range(n_phases // 3):
        e_residuals.append(e_low if (k % 2 == 0) else e_high)

    # Fill phases: E at i%3==0, D at i%3==1, B at i%3==2
    d_counter = 0  # counts D phases to alternate their resolution (D, E, D, E, ...)
    for i in range(n_phases):
        r = i % 3

        if r == 0:  # E
            k = i // 3
            e = e_residuals[k]
            ex[i] = base + e
            de[i] = base

        elif r == 1:  # D (will become U after SHIFT due to incoming excess from left E)
            # Left neighbor is the E at i-1 (since pattern is ...E D B...)
            e_left = e_residuals[(i - 1) // 3]

            if d_counter % 2 == 0:
                # Force U -> D after next BALANCE: d > e_left
                d = e_left + 1
            else:
                # Force U -> E after next BALANCE: d < e_left
                d = max(1, e_left - 1)

            ex[i] = base
            de[i] = base + d
            d_counter += 1

        else:  # B
            ex[i] = base
            de[i] = base

    return ex, de


import gc
import math
import time
from dataclasses import dataclass
from typing import Callable, Any, Tuple, List

import numpy as np

def init_random_ctx(n: int, ratio_balanced: float = 0.0) -> "Context":
    import random
    n = int(n)
    n_balanced = int(n * ratio_balanced)
    n_unbalanced = n - n_balanced

    def random_energy() -> float:
        return random.random() * 1000.0

    blc = deque([random_energy() for _ in range(n_balanced)])
    ex  = deque([random_energy() for _ in range(n_unbalanced)])
    de  = deque([random_energy() for _ in range(n_unbalanced)])

    while len(blc):
        insert = random.random() <= ratio_balanced
        ex.rotate(1)
        de.rotate(1)
        if insert:
            e = blc.pop()
            ex.append(e)
            de.append(e)

    # init produces the state for the timed function
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx

def init_neg_corr_ctx(n):
    ex = np.linspace(1.0,1000.0, int(n))
    de = ex[-1::-1]
    # init produces the state for the timed function
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx

def init_worst_case(n) -> Context:
    ex, de = build_worst_case_cycle(int(n), base=100, e_low=30, e_high=40)
    ctx = Context(energy_excess_per_phase_initial=ex, energy_deficit_per_phase_initial=de)
    return ctx


def run_ctx(ctx: "Context") -> None:
    # THIS is what is timed (run-only)
    ctx.run_mEfES()


def run_complexity_benchmark():
    @dataclass
    class FitResult:
        a: float
        b: float
        r2: float
        n: np.ndarray
        t: np.ndarray  # run-only median seconds per call

    def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
        ss_res = np.sum((y - yhat) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        return 1.0 - (ss_res / ss_tot if ss_tot > 0 else float("nan"))

    def fit_powerlaw(n: np.ndarray, t: np.ndarray) -> Tuple[float, float, float]:
        mask = t > 0
        if np.count_nonzero(mask) < 2:
            raise RuntimeError("Need at least 2 positive timing samples to fit a power law.")
        x = np.log(n[mask])
        y = np.log(t[mask])
        b, loga = np.polyfit(x, y, deg=1)
        a = float(np.exp(loga))
        yhat = loga + b * x
        return a, float(b), float(_r2(y, yhat))

    def complexity_benchmark_run_only(
            init_fn: Callable[[int], Any],
            run_fn: Callable[[Any], None],
            n_min: int = 10 ** 2,
            n_max: int = 10 ** 5,
            n_points: int = 12,
            repeats: int = 9,
            min_total_run_time: float = 0.25,
            warmup: int = 1,
            disable_gc: bool = True,
            progress: bool = True,
            print_every: int = 1,
    ) -> FitResult:
        """
        Benchmarks RUN TIME ONLY for run_fn(state), while still calling init_fn(n) once per execution.
        Prints running fit after each n (once >=2 timing points exist), if progress=True.
        """
        if n_min <= 0 or n_max <= 0 or n_min >= n_max:
            raise ValueError("Require 0 < n_min < n_max.")
        if n_points < 2:
            raise ValueError("n_points must be >= 2.")
        if repeats < 3:
            raise ValueError("Use repeats>=3 for a stable median.")

        n_vals = np.unique(np.round(np.logspace(math.log10(n_min), math.log10(n_max), n_points)).astype(int))
        t_vals: List[float] = []

        def run_only_loops(n: int, loops: int) -> float:
            """Total RUN time over `loops` executions (init called each time, not timed)."""
            if disable_gc:
                gc_was_enabled = gc.isenabled()
                gc.disable()
            try:
                total = 0.0
                for _ in range(loops):
                    state = init_fn(n)  # NOT timed
                    t0 = time.perf_counter()
                    run_fn(state)  # timed
                    total += (time.perf_counter() - t0)
                return total
            finally:
                if disable_gc and gc_was_enabled:
                    gc.enable()

        # Warmup (not recorded)
        for _ in range(max(0, warmup)):
            s = init_fn(int(n_vals[0]))
            run_fn(s)

        for i, n in enumerate(n_vals):
            # probe one-call run time (init excluded from probe timing too)
            probe = [run_only_loops(int(n), loops=1) for _ in range(3)]
            one_call = float(np.median(probe))
            loops = 10_000 if one_call <= 0.0 else max(1, int(math.ceil(min_total_run_time / one_call)))

            per_call_samples = []
            for _ in range(repeats):
                total_run = run_only_loops(int(n), loops=loops)
                per_call_samples.append(total_run / loops)

            t_med = float(np.median(per_call_samples))
            t_vals.append(t_med)

            # Running fit + print
            if progress and ((i + 1) % print_every == 0):
                n_arr = np.array(n_vals[: i + 1], dtype=float)
                t_arr = np.array(t_vals, dtype=float)

                if len(t_arr) >= 2 and np.all(t_arr > 0):
                    a, b, r2 = fit_powerlaw(n_arr, t_arr)
                    print(
                        f"FitResults for n in range {int(n_arr[0])} to {int(n_arr[-1])} "
                        f"({len(n_arr)} pts): a={a:.6e}, b={b:.6f}, R²={r2:.6f} | "
                        f"last: n={int(n)}, t={t_med:.6e}s"
                    )
                else:
                    print(
                        f"Collected {len(t_arr)} point(s) so far; need >=2 for fit. "
                        f"last: n={int(n)}, t={t_med:.6e}s"
                    )

        n_arr = np.array(n_vals, dtype=float)
        t_arr = np.array(t_vals, dtype=float)
        a, b, r2 = fit_powerlaw(n_arr, t_arr)
        return FitResult(a=a, b=b, r2=r2, n=n_arr, t=t_arr)

    res = complexity_benchmark_run_only(
        init_fn=lambda n: init_random_ctx(n, ratio_balanced=0.0),
        # init_fn=lambda n: init_neg_corr_ctx(n),
        run_fn=run_ctx,
        n_min=10 ** 2,
        n_max=10 ** 7,
        n_points=12,
        repeats=5,
        min_total_run_time=0.0001,
        warmup=2,
        disable_gc=True,
    )

    print("Fit: t(n) ≈ a * n^b   (RUN-ONLY; init excluded)")
    print(f"a  = {res.a:.6e}")
    print(f"b  = {res.b:.6f}")
    print(f"R² = {res.r2:.6f}")
    print("\nSamples (median seconds per call, run-only):")
    for n, t in zip(res.n.astype(int), res.t):
        print(f"n={n:>7d}  t={t:.6e}")


def run_worst_case(n):
    ctx = init_worst_case(n)
    ctx.run_mEfES()

def run_random(n):
    ctx = init_random_ctx(n)
    ctx.run_mEfES()

if __name__ == "__main__":

    run_example()
    #run_worst_case(n=1000)
    #run_random(n=100000)
    #run_complexity_benchmark()

