## Effective Energy Shift (EfES) algorithm for Electric Energy Storage (EES) analysis

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/AirborneKiwi/effective_energy_shift.git/HEAD?labpath=demo_notebook.ipynb)

This repository contains the code for the Effective Energy Shift (EfES) and the more Effective Energy Shift (mEfES) algorithms. 
The EfES algorithm is described in ["The Effective Energy Shift (EfES) algorithm: A non-iterative piece-wise linear method for mapping storage capacity to self-sufficiency and self-consumption" by J. Fellerer, D. Scharrer, and R. German, published in Applied Energy, 2026](https://doi.org/10.1016/j.apenergy.2025.127241).
Please cite the publication according to your guidelines, when utilizing the code from this repo.

It is implemented in Python and an interactive demonstration of the algorithm can be run in the cloud using Binder by clicking on the "launch binder" badge above.

## Installation

Clone the repository and install the required packages using conda:

```bash
conda env create -f environment.yml -n efes_env
conda activate efes_env
```

## Minimal example

Since the algorithm requires time series for generation and demand power as input, we will use the following example data:

```python
import mefes
from efes_core import EfesInput

# Define the input data
power_generation, power_demand = mefes.examples.build_example_time_series()
efes_input = EfesInput(
    power_generation=power_generation,
    power_demand=power_demand,
    delta_time_step=1.,
)
# Run the algorithm (mEfES implementation)
results = mefes.run(efes_input)

# Print the result
print(results.analysis_results.capacity)
print(results.analysis_results.energy_additional)
print(results.analysis_results.self_sufficiency)
print(results.analysis_results.self_consumption)
```

## Interactive visualization
A more elaborate example can be found in the jupyter notebook [demo_notebook.ipynb](demo_notebook.ipynb), which can be launched using the "launch binder" badge above.
The interactive visualization available in it is shown below:

![interactive_visualization_in_demo_notebook.jpg](examples%2Finteractive_visualization_in_demo_notebook.jpg)

## License

The code is provided under the MIT license. If you use the code in your research, please cite the paper above.

## Contact

If you have any questions, please contact the authors of the paper via <jonathan.fellerer@fau.de>.

