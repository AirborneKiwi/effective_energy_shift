from __future__ import annotations

from typing import List, Tuple

from mefes.domain.errors import ValidationError
from mefes.domain.models import MefesState

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

    if n_phases <= 1:
        raise ValidationError("n_phase_pairs must be greater than 1")

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
