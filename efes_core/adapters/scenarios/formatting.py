from __future__ import annotations

from typing import Union
import numpy as np

def get_scaling(num: Union[np.ndarray, float, int]):
    try:
        return list(map(get_scaling, num))
    except Exception:
        pass

    if num == 0:
        return 1.0, ""
    if abs(num) > 1e12:
        return 1e-12, "T"
    if abs(num) > 1e9:
        return 1e-9, "G"
    if abs(num) > 1e6:
        return 1e-6, "M"
    if abs(num) > 1e3:
        return 1e-3, "k"
    if abs(num) < 1e-6:
        return 1e6, "u"
    if abs(num) < 1e-3:
        return 1e3, "m"
    return 1.0, ""


def get_num_from_str_with_scale_and_unit(num_str: Union[np.ndarray, str], unit: str):
    if isinstance(num_str, list):
        return list(map(lambda v: get_num_from_str_with_scale_and_unit(v, unit), num_str))
    if not isinstance(num_str, str):
        return num_str
    scales = {"T": 1e12, "G": 1e9, "M": 1e6, "k": 1e3, "": 1.0, "m": 1e-3, "u": 1e-6}
    for prefix, scale in scales.items():
        suffix = f" {prefix}{unit}"
        if num_str.endswith(suffix):
            return float(num_str[: -len(suffix)]) * scale
    return float(num_str)


def pretty_print(num: Union[np.ndarray, float, int], unit: str, decimals: int = 2):
    try:
        return [pretty_print(v, unit=unit, decimals=decimals) for v in num]
    except Exception:
        scale, prefix = get_scaling(num)
        return f"{num * scale:.{decimals}f} {prefix}{unit}"
