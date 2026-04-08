from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

import mefes
import efes
from efes_core import EfesInput, QueryInput, Results, run_chrono_ref_alg

def get_example_input(impl: str = 'mefes') -> EfesInput:
    """Get the example input for a specific implementation: 'efes' or 'mefes'"""
    match impl.lower():
        case 'efes':
            power_generation, power_demand =  efes.examples.build_example_time_series()
        case 'mefes':
            power_generation, power_demand =  mefes.examples.build_example_time_series()
        case _:
            raise AttributeError(f'Implementation "{impl}" not known. Use "efes" or "mefes"')

    return EfesInput(
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=1.
    )


def create_tabel_from_results(*results: Any) -> pd.DataFrame:
    """
    Build a comparison table from multiple Results objects.

    Expected structure per result:
        result.analysis_results.used_method -> str
        result.query_results[0].capacity -> array-like
        result.query_results[0].energy_additional -> array-like

    Output columns follow the same order as the passed results, with delta columns
    inserted between adjacent result columns.

    Example column order for:
        create_tabel_from_results(ref_res, efes_res, mefes_res)

    becomes:
        capacity,
        Chrono. ref.,
        delta(Chrono. ref.-EfES),
        EfES,
        delta(EfES-mEfES),
        mEfES
    """
    if not results:
        raise ValueError("At least one result object must be provided.")

    # Extract first query result from each implementation
    extracted = []
    for result in results:
        impl_name = getattr(result.analysis_results, "used_method", None)
        if impl_name is None:
            raise AttributeError(f"Missing 'used_method' field on result object: {result!r}")

        query_results = getattr(result, "query_results", None)
        if not query_results:
            raise ValueError(f"Result object '{impl_name}' has no query_results.")

        qr = query_results[0]

        capacity = np.asarray(getattr(qr, "capacity"))
        energy_additional = np.asarray(getattr(qr, "energy_additional"))

        extracted.append(
            {
                "impl": impl_name,
                "capacity": capacity,
                "energy_additional": energy_additional,
            }
        )

    # Validate that all capacities are identical
    ref_capacity = extracted[0]["capacity"]
    for item in extracted[1:]:
        if not np.array_equal(ref_capacity, item["capacity"]):
            raise ValueError(
                f"Capacity mismatch between '{extracted[0]['impl']}' and '{item['impl']}'."
            )

    # Build dataframe in requested order
    data: dict[str, np.ndarray] = {
        "capacity": ref_capacity
    }

    for i, item in enumerate(extracted):
        impl = item["impl"]
        values = item["energy_additional"]

        data[impl] = values

        if i < len(extracted) - 1:
            next_item = extracted[i + 1]
            next_impl = next_item["impl"]
            delta_col = f"delta({impl}-{next_impl})"
            data[delta_col] = values - next_item["energy_additional"]

    return pd.DataFrame(data)


if __name__ == "__main__":
    example_input = get_example_input("mefes")
    query_input = QueryInput(
        capacity_target=[0., 1., 2., 3., 4., 5., 6., 7., 9., 11., 13., 15.,20.]
    )

    efes_res = efes.run(
        efes_input=example_input,
        query_input=query_input,
    )

    mefes_res = mefes.run(
        efes_input=example_input,
        query_input=query_input,
    )

    ref_res = run_chrono_ref_alg(
        efes_input=example_input,
        query_input=query_input,
        capacity_bounds=(0, 20),
        n_samples=1000,
    )
    print(mefes_res)

    df = pd.DataFrame(columns=['Cstart', 'Cend', 'm', 'E'],
                      data={
                          'Cstart': [*mefes_res.analysis_results.capacity, 2*mefes_res.analysis_results.capacity[-1]],
                          'Cend': [*mefes_res.analysis_results.capacity[1:], 2*mefes_res.analysis_results.capacity[-1], 2*mefes_res.analysis_results.capacity[-1]],
                          'E': [*mefes_res.analysis_results.energy_additional, mefes_res.analysis_results.energy_additional[-1]],
                          'm': [*mefes_res.analysis_results.effectiveness_local, 0]
                      })

    print(df.to_markdown())
    df.to_csv("results_compressed.csv", index=False, float_format="%.6f")

    df = create_tabel_from_results(ref_res, efes_res, mefes_res)
    df.columns = [
        "capacity",
        "chronoRef",
        "deltaChronoRefEfes",
        "efes",
        "deltaEfesMefes",
        "mefes"
    ]

    print(df.transpose().to_markdown())

    df.transpose().to_csv("comparison_results.csv", header=False, index=True, float_format="%.2f")