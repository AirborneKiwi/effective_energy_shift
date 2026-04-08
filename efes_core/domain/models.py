from dataclasses import dataclass, is_dataclass, asdict, fields
from typing import Any, Optional, Dict

import numpy as np
import pandas as pd

from efes_core.domain.errors import PacketValidationError

@dataclass(slots=True)
class AlgorithmState:
    step: str = "NOT_INITIALIZED"


EPS = 1e-8


def _normalize_array_like(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Series):
        return value.to_numpy()
    if isinstance(value, tuple):
        return np.asarray(value)
    if isinstance(value, list):
        # keep lists of nested dataclasses as lists
        if value and all(isinstance(v, (dict, QueryResults, Results)) for v in value):
            return value
        return np.asarray(value)
    return value


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="list")
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if is_dataclass(value):
        data = {k: _serialize_value(v) for k, v in asdict(value).items() if v is not None}
        data["type_info"] = type(value).__name__
        return data
    return value


def pretty(obj, indent=0):
    pad = " " * indent

    if is_dataclass(obj):
        lines = [f"{obj.__class__.__name__}("]
        for f in fields(obj):
            value = pretty(getattr(obj, f.name), indent + 2)
            lines.append(f"{' ' * (indent + 2)}{f.name}={value},")
        lines.append(f"{pad})")
        return "\n".join(lines)

    if isinstance(obj, np.ndarray):
        return np.array2string(obj, threshold=100, edgeitems=2, precision=3, suppress_small=True)

    if isinstance(obj, np.generic):
        return repr(obj.item())

    return repr(obj)


class PrettyRepr:
    def __repr__(self):
        return pretty(self)


@dataclass(repr=False)
class EnergyPacket(PrettyRepr):
    capacity: float
    energy: float

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise PacketValidationError("capacity must be non-negative")
        if self.energy <= 0:
            raise PacketValidationError("energy must be positive")

    @property
    def capacity_max(self) -> float:
        return self.capacity + self.energy

    @property
    def start(self) -> float:
        return self.capacity

    @property
    def end(self) -> float:
        return self.capacity_max

    def precedes(self, other: "EnergyPacket") -> bool:
        return self.end <= other.start + EPS

    def starts_below_level(self, level: float) -> bool:
        return self.start + EPS < level

    def starts_at_or_above_level(self, level: float) -> bool:
        return not self.starts_below_level(level)

    def starts_below(self, other: "EnergyPacket") -> bool:
        return self.start + EPS < other.start

    def starts_above(self, other: "EnergyPacket") -> bool:
        return self.start > other.end + EPS

    def starts_within(self, other: "EnergyPacket") -> bool:
        return not (self.starts_below(other) or self.starts_above(other))

    def ends_below(self, other: "EnergyPacket") -> bool:
        return self.end + EPS < other.start

    def ends_above(self, other: "EnergyPacket") -> bool:
        return self.end > other.end + EPS

    def ends_within(self, other: "EnergyPacket") -> bool:
        return not (self.ends_below(other) or self.ends_above(other))

    def _delta(self, other: "EnergyPacket") -> float:
        left = max(self.capacity, other.capacity)
        right = min(self.capacity_max, other.capacity_max)
        return right - left

    def overlaps_with(self, other: "EnergyPacket") -> bool:
        return self._delta(other) >= -EPS

    def contact_with(self, other: "EnergyPacket") -> bool:
        return abs(self._delta(other)) <= EPS

    def overlap_or_contact(self, other: "EnergyPacket") -> bool:
        return self.overlaps_with(other)

    def overlaps_strictly_with(self, other: "EnergyPacket") -> bool:
        return self._delta(other) > EPS

    def lift_to(self, level: float) -> "EnergyPacket":
        if self.starts_below_level(level):
            self.capacity = level
        return self


@dataclass(slots=True,repr=False)
class EfesInput(PrettyRepr):
    power_generation: Any = None
    power_demand: Any = None
    delta_time_step: Optional[float] = None
    power_used_generation: Optional[np.ndarray] = None
    power_covered_demand: Optional[np.ndarray] = None
    power_residual_generation: Optional[np.ndarray] = None
    power_max_discharging: float = np.inf
    power_max_charging: float = np.inf
    efficiency_direct_usage: float = 1.0
    efficiency_discharging: float = 1.0
    efficiency_charging: float = 1.0

    def __post_init__(self) -> None:
        self.power_generation = _normalize_array_like(self.power_generation)
        self.power_demand = _normalize_array_like(self.power_demand)
        self.power_used_generation = _normalize_array_like(self.power_used_generation)
        self.power_covered_demand = _normalize_array_like(self.power_covered_demand)
        self.power_residual_generation = _normalize_array_like(self.power_residual_generation)
       
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = _serialize_value(self)
        if not add_type_info:
            payload.pop("type_info", None)
        return payload


@dataclass(slots=True,repr=False)
class QueryInput(PrettyRepr):
    self_sufficiency_target: Any = None
    self_consumption_target: Any = None
    energy_additional_target: Any = None
    capacity_target: Any = None

    def __post_init__(self) -> None:
        self.self_sufficiency_target = _normalize_array_like(self.self_sufficiency_target)
        self.self_consumption_target = _normalize_array_like(self.self_consumption_target)
        self.energy_additional_target = _normalize_array_like(self.energy_additional_target)
        self.capacity_target = _normalize_array_like(self.capacity_target)

    def count_targets(self) -> int:
        return sum(
            target is not None
            for target in (
                self.self_sufficiency_target,
                self.self_consumption_target,
                self.energy_additional_target,
                self.capacity_target,
            )
        )

    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = _serialize_value(self)
        if not add_type_info:
            payload.pop("type_info", None)
        return payload


@dataclass(slots=True,repr=False)
class DimensioningResults(PrettyRepr):
    capacity: Any = None
    energy_additional: Any = None
    self_sufficiency: Any = None
    self_consumption: Any = None
    effectiveness: Any = None
    effectiveness_local: Any = None
    gain: Any = None

    def __post_init__(self) -> None:
        self.capacity = _normalize_array_like(self.capacity)
        self.energy_additional = _normalize_array_like(self.energy_additional)
        self.self_sufficiency = _normalize_array_like(self.self_sufficiency)
        self.self_consumption = _normalize_array_like(self.self_consumption)
        self.effectiveness = _normalize_array_like(self.effectiveness)
        self.effectiveness_local = _normalize_array_like(self.effectiveness_local)
        self.gain = _normalize_array_like(self.gain)


@dataclass(slots=True,repr=False)
class AnalysisResults(DimensioningResults):
    data_input: Optional[EfesInput] = None

    energy_used_generation: Optional[float] = None
    energy_covered_demand: Optional[float] = None
    energy_demand: Optional[float] = None
    energy_generation: Optional[float] = None

    power_residual_generation_clipped: Any = None

    self_sufficiency_initial: Optional[float] = None
    self_consumption_initial: Optional[float] = None

    time_total: Optional[float] = None
    starts_phases: Any = None
    lengths_phases: Any = None
    values_phases: Any = None
    N_phases: Optional[int] = None

    energy_excess_wo_efficiency: Any = None
    energy_excess: Any = None
    energy_deficit_wo_efficiency: Any = None
    energy_deficit_wo_debt: Any = None
    energy_deficit: Any = None

    capacity_max: Optional[float] = None
    energy_additional_max: Optional[float] = None
    self_sufficiency_max: Optional[float] = None
    self_consumption_max: Optional[float] = None

    used_method: str = None

    def __post_init__(self) -> None:
        DimensioningResults.__post_init__(self)
        if self.data_input is not None and not isinstance(self.data_input, EfesInput):
            self.data_input = EfesInput(**self.data_input)
        for attr in (
                "power_residual_generation_clipped",
                "starts_phases",
                "lengths_phases",
                "values_phases",
                "energy_excess_wo_efficiency",
                "energy_excess",
                "energy_deficit_wo_efficiency",
                "energy_deficit_wo_debt",
                "energy_deficit",
                "effectiveness_local",
        ):
            setattr(self, attr, _normalize_array_like(getattr(self, attr)))


    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = _serialize_value(self)
        if not add_type_info:
            payload.pop("type_info", None)
        return payload


@dataclass(slots=True,repr=False)
class QueryResults(DimensioningResults):
    query_input: Optional[QueryInput] = None
    effectiveness_local: Any = None
    effectiveness: Any = None
    gain_per_day: Any = None

    def __post_init__(self) -> None:
        DimensioningResults.__post_init__(self)
        if self.query_input is not None and not isinstance(self.query_input, QueryInput):
            self.query_input = QueryInput(**self.query_input)
        self.effectiveness_local = _normalize_array_like(self.effectiveness_local)
        self.effectiveness = _normalize_array_like(self.effectiveness)
        self.gain_per_day = _normalize_array_like(self.gain_per_day)

    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = _serialize_value(self)
        if not add_type_info:
            payload.pop("type_info", None)
        return payload


@dataclass(slots=True,repr=False)
class Results(PrettyRepr):
    analysis_results: Optional[AnalysisResults] = None
    query_results: Optional[list[QueryResults]] = None

    def __post_init__(self) -> None:
        if self.analysis_results is not None and not isinstance(self.analysis_results, AnalysisResults):
            self.analysis_results = AnalysisResults(**self.analysis_results)
        if self.query_results is not None:
            self.query_results = [item if isinstance(item, QueryResults) else QueryResults(**item) for item in
                                  self.query_results]

    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = _serialize_value(self)
        if not add_type_info:
            payload.pop("type_info", None)
        return payload


@dataclass(slots=True,repr=False)
class ParameterStudyResults(PrettyRepr):
    parameter_variation: Optional[pd.DataFrame] = None
    results: Optional[list[Any]] = None

    def __post_init__(self) -> None:
        if isinstance(self.parameter_variation, dict):
            self.parameter_variation = pd.DataFrame(data=self.parameter_variation)
        if self.results is not None:
            converted = []
            for item in self.results:
                if isinstance(item, (Results, str)):
                    converted.append(item)
                else:
                    converted.append(Results(**item))
            self.results = converted

    def to_json_dict(self, add_type_info: bool = False) -> dict[str, Any]:
        payload = {
            "parameter_variation": None if self.parameter_variation is None else self.parameter_variation.to_dict(
                orient="list"),
            "results": _serialize_value(self.results),
        }
        if add_type_info:
            payload["type_info"] = type(self).__name__
        return payload


