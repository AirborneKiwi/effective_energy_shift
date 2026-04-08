from __future__ import annotations

from typing import Optional, List, Tuple

import numpy as np

from efes_core.domain.models import EnergyPacket
from .models import Phase, EfesState


def balance_phase(phase: Phase):
    start_max = max(phase.starts_excess[-1], phase.starts_deficit[-1])
    phase.starts_excess[-1] = start_max
    phase.starts_deficit[-1] = start_max
    phase.excess_balanced[-1] = True

    if phase.energy_excess[-1] == phase.energy_deficit[-1]:
        phase.deficit_balanced[-1] = True
        return False, False

    if phase.energy_excess[-1] > phase.energy_deficit[-1]:
        phase.deficit_balanced[-1] = True
        new_start = phase.starts_deficit[-1] + phase.energy_deficit[-1]
        energy_remaining = phase.energy_excess[-1] - phase.energy_deficit[-1]

        phase.energy_excess[-1] = phase.energy_deficit[-1]
        phase.starts_excess = np.append(phase.starts_excess, new_start)
        phase.energy_excess = np.append(phase.energy_excess, energy_remaining)
        phase.excess_balanced = np.append(phase.excess_balanced, False)
        phase.excess_ids = np.append(phase.excess_ids, phase.excess_ids[-1])
        return True, False

    new_start = phase.starts_excess[-1] + phase.energy_excess[-1]
    energy_remaining = phase.energy_deficit[-1] - phase.energy_excess[-1]
    phase.energy_deficit[-1] = phase.energy_excess[-1]
    phase.deficit_balanced[-1] = True
    phase.starts_deficit = np.append(phase.starts_deficit, new_start)
    phase.energy_deficit = np.append(phase.energy_deficit, energy_remaining)
    phase.deficit_balanced = np.append(phase.deficit_balanced, False)
    return False, True


def calculate_virtual_excess(current_phase: Phase, next_phase: Phase):
    overflow_content = current_phase.energy_excess[-1]
    overflow_start = current_phase.starts_excess[-1]
    blocking_excess_content = next_phase.energy_excess[-1]
    blocking_excess_start = next_phase.starts_excess[-1]
    virtual_excess_start = max(overflow_start, blocking_excess_start + blocking_excess_content)
    virtual_excess_content = overflow_content
    virtual_excess_id = current_phase.excess_ids[-1]
    return virtual_excess_start, virtual_excess_content, virtual_excess_id


def add_excess_to_phase(phase: Phase, excess_start, excess_content, excess_id):
    phase.starts_excess = np.append(phase.starts_excess, excess_start)
    phase.energy_excess = np.append(phase.energy_excess, excess_content)
    phase.excess_balanced = np.append(phase.excess_balanced, False)
    phase.excess_ids = np.append(phase.excess_ids, excess_id)


def remove_excess(phase: Phase, index_to_remove: int):
    phase.energy_excess = np.delete(phase.energy_excess, obj=index_to_remove)
    phase.starts_excess = np.delete(phase.starts_excess, obj=index_to_remove)
    phase.excess_balanced = np.delete(phase.excess_balanced, obj=index_to_remove)
    phase.excess_ids = np.delete(phase.excess_ids, obj=index_to_remove)


def extract_energy_packets(efes_state: EfesState) -> List[EnergyPacket]:
    energy_packets = []
    for phase in efes_state.phases:
        energy_packets.extend([EnergyPacket(c,e) for (c,e) in zip(phase.starts_deficit[phase.deficit_balanced], phase.energy_deficit[phase.deficit_balanced])])
    return energy_packets


