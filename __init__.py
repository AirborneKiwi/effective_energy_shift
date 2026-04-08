from __future__ import annotations

import dataclasses
from typing import Dict, Any

from efes.application.use_cases import EfesImplementation
from efes_core.application.use_cases import EfesAlgorithmRunner
from efes_core.domain.errors import ImplementationNotKnown
from efes_core.domain.models import Results, EfesInput, QueryInput
from efes_core.domain.ports import EfesImplementationPort
from mefes.adapters.scenarios.example_inputs import build_example_time_series
from mefes.application.use_cases import MefesImplementation
from mefes.domain.ports import MefesObserverPort

def get_example_input() -> EfesInput:
    power_generation, power_demand = build_example_time_series()
    efes_input = EfesInput(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=1.0,
    )
    return efes_input

def run(efes_input:EfesInput,
        query_input:QueryInput|None=None,
        observer: MefesObserverPort|None=None,
        impl: EfesImplementationPort|None=None,
        model: str='mefes',
        ) -> Results:

    if impl is None:
        match model.lower():
            case "efes":
                impl = EfesImplementation(observer=observer)
            case "mefes":
                impl = MefesImplementation(observer=observer)
            case _:
                raise ImplementationNotKnown(f'The implementation model "{model}" is not known. Use "efes" or "mefes" (default).')


    alg_runner = EfesAlgorithmRunner(impl=impl, observer=observer)

    def as_dict(obj, skip_none=True) -> Dict[str, Any]:
        res = dict()
        if obj is None:
            return res
        for k, v in dataclasses.asdict(obj).items():
            if v is None and skip_none:
                continue
            res[k] = v
        return res

    alg_runner.initialize(**as_dict(efes_input))

    alg_runner.execute()

    results = alg_runner.query(**as_dict(query_input))
    return results