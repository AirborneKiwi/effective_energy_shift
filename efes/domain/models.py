from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, List

import numpy as np

from efes_core.domain.models import _normalize_array_like, AlgorithmState


@dataclass(slots=True)
class EfesState(AlgorithmState):
    """
    State container only.
    Algorithmic orchestration belongs in an application service / use case.
    """
    phases: Optional[List[Phase]] = None
    phase_data_deficit: Optional[List[PhaseData]] = None
    phase_data_excess: Optional[List[PhaseData]] = None
    mask: List[List[bool]] = None

    def __post_init__(self) -> None:
        if self.phase_data_deficit is not None:
            self.phase_data_deficit = [item if isinstance(item, PhaseData) else PhaseData(**item) for item in
                                       self.phase_data_deficit]
        if self.phase_data_excess is not None:
            self.phase_data_excess = [item if isinstance(item, PhaseData) else PhaseData(**item) for item in
                                      self.phase_data_excess]

@dataclass(slots=True)
class Phase:
    energy_excess_initial: float
    energy_deficit_initial: float
    id: Optional[float] = None
    starts_excess: np.ndarray = field(init=False)
    starts_deficit: np.ndarray = field(init=False)
    energy_excess: np.ndarray = field(init=False)
    energy_deficit: np.ndarray = field(init=False)
    excess_balanced: np.ndarray = field(init=False)
    deficit_balanced: np.ndarray = field(init=False)
    excess_ids: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.starts_excess = np.array([0.0])
        self.starts_deficit = np.array([0.0])
        self.energy_excess = np.array([self.energy_excess_initial])
        self.energy_deficit = np.array([self.energy_deficit_initial])
        self.excess_balanced = np.array([False])
        self.deficit_balanced = np.array([False])
        self.excess_ids = np.array([self.id])

    def __str__(self) -> str:
        return (
            f"Phase {self.id}:\n"
            f"starts_excess={self.starts_excess}, energy_excess={self.energy_excess}, "
            f"excess_balanced={self.excess_balanced}, excess_ids={self.excess_ids}\n"
            f"starts_deficit={self.starts_deficit}, energy_deficit={self.energy_deficit}, "
            f"deficit_balanced={self.deficit_balanced}\n"
        )


@dataclass(slots=True)
class PhaseData:
    power: Any = None
    duration: Any = None
    energy: Any = None

    def __post_init__(self) -> None:
        self.power = _normalize_array_like(self.power)
        self.duration = _normalize_array_like(self.duration)
        self.energy = _normalize_array_like(self.energy)

