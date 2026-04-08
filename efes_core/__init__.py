from typing import Tuple

from efes_core.application.use_cases import ChronoRefImpl, EfesAlgorithmRunner
from efes_core.domain.models import EfesInput, QueryInput, _serialize_value, Results
from efes_core.domain.ports import ObserverPort
from efes_core.scripts import chronological_ref_alg

# expose serialization for dict conversion
model_dump = _serialize_value

def run_chrono_ref_alg(efes_input: EfesInput, capacity_bounds:Tuple[float], n_samples:int, query_input: QueryInput=None, observer: ObserverPort = None) -> Results:
    impl = ChronoRefImpl(
        capacity_min=capacity_bounds[0],
        capacity_max=capacity_bounds[1],
        n_samples=n_samples,
        observer=observer
    )
    alg_runner = EfesAlgorithmRunner(impl=impl, observer=observer)

    alg_runner.initialize(
        power_generation=efes_input.power_generation,
        power_demand=efes_input.power_demand,
        delta_time_step=efes_input.delta_time_step,
        power_max_charging=efes_input.power_max_charging,
        power_max_discharging=efes_input.power_max_discharging,
        efficiency_charging=efes_input.efficiency_charging,
        efficiency_discharging=efes_input.efficiency_discharging,
        efficiency_direct_usage=efes_input.efficiency_direct_usage,
    )
    alg_runner.execute()

    if query_input is None:
        query_input = QueryInput()

    results: Results = alg_runner.query(
        capacity_target=query_input.capacity_target,
        energy_additional_target=query_input.energy_additional_target,
        self_consumption_target=query_input.self_consumption_target,
        self_sufficiency_target=query_input.self_sufficiency_target,
    )

    return results