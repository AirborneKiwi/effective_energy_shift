from efes_core.domain.models import EfesInput, Results, QueryInput
from efes_core.domain.ports import ObserverPort
from efes_core.application.use_cases import EfesAlgorithmRunner
import mefes.adapters.scenarios.example_inputs as examples
from mefes.application.use_cases import MefesImplementation

def run(efes_input: EfesInput, query_input: QueryInput=None, observer: ObserverPort = None) -> Results:
    impl = MefesImplementation(observer=observer)
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