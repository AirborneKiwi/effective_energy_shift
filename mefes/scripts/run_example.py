from __future__ import annotations

import numpy as np

from efes.adapters.observability.plotting_observer import PlottingObserver
from efes.application.use_cases import EfesImplementation
from efes.domain.models import EfesState
from efes.domain.services import extract_energy_packets
from efes_core.adapters.scenarios.plotting import plot_input, plot_results, save_figure
from efes_core.application.use_cases import EfesAlgorithmRunner, ChronoRefImpl
from efes_core.domain.models import Results, AnalysisResults
from mefes.adapters.observability.logging_observer import ConsoleLoggingObserver
from mefes.adapters.scenarios.example_inputs import build_example_time_series
from mefes.application.use_cases import MefesImplementation
from mefes.domain.models import MefesState
from mefes.scripts._common import print_final_summary


def main(
    log_to_console: bool = True,
    bootstrap_tests:bool = False,
    bootstrap_event_recording:bool = False,
    bootstrap_tex_output:bool = False,
) -> Results:
    if bootstrap_tests:
        from mefes.debug.bootstrap_debug import bootstrap
        bootstrap('test')
    if bootstrap_event_recording:
        from mefes.debug.bootstrap_debug import bootstrap
        evt_rec = bootstrap('event_recording')
    if bootstrap_tex_output:
        from mefes.debug.bootstrap_debug import bootstrap
        bootstrap('tex_output')

    data_input = dict(
        delta_time_step=1.0,
        #efficiency_charging=0.6,
        #efficiency_discharging=0.7,
        #efficiency_direct_usage=0.9,
    )
    query_input = dict(
        capacity_target=np.array([0, 1, 2, 3, 5, 6, 7, 8, 10, 12, 18])
    )

    power_generation, power_demand = build_example_time_series(
        efficiency_direct_usage=data_input.get('efficiency_direct_usage', 1)
    )

    data_input['power_generation'] = power_generation
    data_input['power_demand'] = power_demand

    observer = None
    if log_to_console:
        observer = ConsoleLoggingObserver(enabled=True, verbose_groups=True)

    mefes_impl = MefesImplementation(observer=observer)
    mefes_alg_runner = EfesAlgorithmRunner(impl=mefes_impl, observer=observer)



    analysis_results: AnalysisResults = mefes_alg_runner.initialize(**data_input)

    mefes_alg_runner.execute()

    mefes_results: Results = mefes_alg_runner.query(**query_input)

    if bootstrap_event_recording:
        print(evt_rec.module.EventRecorder())

    # run EfES
    efes_alg_runner = EfesAlgorithmRunner(impl=EfesImplementation(observer=PlottingObserver(
            efficiency_discharging=1,
            show=False,
            save_frames=True,
            output_dir="debug_energy_packets",
        ),))
    efes_alg_runner.initialize(**data_input)
    efes_alg_runner.execute()

    eps = []
    for ep in extract_energy_packets(efes_alg_runner.impl.state):
        eps.append((float(ep.capacity), float(ep.energy)))
    print('EfES energy packets are:')
    print(eps)

    efes_results: Results = efes_alg_runner.query(**query_input)

    # run chronological reference
    chrono_alg_runner = EfesAlgorithmRunner(
        impl=ChronoRefImpl(
            capacity_min=0,
            capacity_max=20,
            n_samples=10000
        )
    )
    chrono_alg_runner.initialize(**data_input)
    ref_result: AnalysisResults = chrono_alg_runner.execute()
    ref_result = Results(analysis_results=ref_result)

    for res, name in [(mefes_results, 'mefes'), (efes_results, 'efes'), (ref_result, 'ref')]:
        print(f'\n -------- {name} ------- \n')
        fig_input, _ = plot_input(res, show=False)
        fig_results, _ = plot_results(res, show=False, xlim=[0,15])
        save_figure(fig_input, f"{name}_input.png")
        save_figure(fig_results, f"{name}_results.png")

        print("capacity_max:", res.analysis_results.capacity_max)
        print("energy_additional_max:", res.analysis_results.energy_additional_max)
        print("capacity:", res.analysis_results.capacity)
        print("energy_additional:", res.analysis_results.energy_additional)
        print("marginal effectiveness:", res.analysis_results.effectiveness_local)
        if res.query_results:
            print("query capacities:", res.query_results[0].capacity)
            print("query additional energy:", res.query_results[0].energy_additional)
            print("query marginal effectiveness:", res.query_results[0].effectiveness_local)
            print("saved figures: example_input.png, example_results.png")

    return mefes_results


if __name__ == "__main__":
    main()
