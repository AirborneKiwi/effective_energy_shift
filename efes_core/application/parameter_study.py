from efes_core.application.use_cases import EfesAlgorithmRunner
from efes_core.domain.models import ParameterStudyResults
from efes_core.domain.ports import ParameterStudyStorePort


def run_parameter_study(
    runner: EfesAlgorithmRunner,
    power_generation,
    power_demand,
    delta_time_step,
    parameter_variation,
    store: ParameterStudyStorePort,
    **kwargs,
) -> ParameterStudyResults:
    parameter_variation = parameter_variation.copy()
    parameter_variation["basecase"] = parameter_variation.index
    basecase_max = parameter_variation["basecase"].max()
    parameter_variation["basecase"] = parameter_variation["basecase"].map(
        lambda value: f"{value:0{len(str(basecase_max))}d}"
    )

    store.prepare(parameter_variation=parameter_variation)
    result_refs: list[str] = []

    for _, variation in parameter_variation.iterrows():
        basecase = variation["basecase"]
        call_kwargs = {**kwargs, **variation.drop(labels=["basecase"]).to_dict()}
        if store.exists(basecase):
            result_refs.append(store.load_result_reference(basecase))
            continue

        runner.initialize(
            power_generation=power_generation,
            power_demand=power_demand,
            delta_time_step=delta_time_step,
            **call_kwargs,
        )
        result = runner.execute()
        result = runner.query(**call_kwargs)
        result_refs.append(store.save_result(basecase, result))

    return store.build_output(parameter_variation=parameter_variation, results=result_refs)
