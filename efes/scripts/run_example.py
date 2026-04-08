from __future__ import annotations

import numpy as np

from efes.adapters.scenarios.example_inputs import build_example_time_series
from efes_core.adapters.observability.logging_observer import LoggingObserver
from efes.adapters.observability.plotting_observer import PlottingObserver

from efes.application.use_cases import EfesImplementation
from efes_core.adapters.observability.observers import CompositeObserver
from efes_core.adapters.scenarios.plotting import plot_input, plot_results, save_figure

from efes_core.application.use_cases import EfesAlgorithmRunner, ChronoRefImpl
from efes_core.domain.models import AnalysisResults, Results
from efes_core.scripts.chronological_ref_alg import query_capacities

if __name__ == "__main__":
    power_generation, power_demand = build_example_time_series()

    observer = CompositeObserver(
        LoggingObserver(),
        PlottingObserver(
            efficiency_discharging=0.9,
            show=False,
            save_frames=True,
            output_dir="debug_energy_packets",
        ),
    )

    efes_impl = EfesImplementation(observer=observer)
    efes_alg_runner = EfesAlgorithmRunner(impl=efes_impl, observer=observer)

    data_input = dict(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=1.0,
        efficiency_charging=0.6,
        efficiency_discharging=0.7,
        efficiency_direct_usage=0.9,
    )
    query_input = dict(
        capacity_target=np.array([0, 1, 2, 3, 5, 6, 8, 10, 12])
    )

    analysis_results: AnalysisResults = efes_alg_runner.initialize(**data_input)

    efes_alg_runner.execute()

    results: Results = efes_alg_runner.query(**query_input)

    chrono_alg = ChronoRefImpl(capacity_min=0, capacity_max=15, n_samples=10000)
    chrono_alg_runner = EfesAlgorithmRunner(impl=chrono_alg)
    chrono_alg_runner.initialize(**data_input)
    ref_result: AnalysisResults = chrono_alg_runner.execute()
    ref_result = Results(analysis_results=ref_result)

    for res, name in [(results, 'efes'), (ref_result, 'ref')]:

        fig_input, _ = plot_input(res, show=False)
        fig_results, _ = plot_results(res, show=False)
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
