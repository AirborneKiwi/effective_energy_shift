from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from efes_core.domain.models import Results, AnalysisResults, QueryResults, EfesInput, QueryInput, ParameterStudyResults

REGISTRY = {
    "Results": Results,
    "AnalysisResults": AnalysisResults,
    "QueryResults": QueryResults,
    "EfesInput": EfesInput,
    "QueryInput": QueryInput,
    "ParameterStudyResults": ParameterStudyResults,
}


def from_json_dict(payload: Any) -> Any:
    if isinstance(payload, list):
        return [from_json_dict(item) for item in payload]
    if isinstance(payload, dict):
        type_info = payload.get("type_info")
        converted = {key: from_json_dict(value) for key, value in payload.items() if key != "type_info"}
        if type_info in REGISTRY:
            return REGISTRY[type_info](**converted)
        return converted
    return payload


def write_to_json(obj: Any, filename: str, indent: int = 2) -> Path:
    path = Path(filename)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    with path.open("w", encoding="utf-8") as file:
        json.dump(obj.to_json_dict(add_type_info=True), file, indent=indent)
    return path


def read_from_json(filename: str) -> Any:
    path = Path(filename)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return from_json_dict(payload)
