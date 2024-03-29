## Effective Energy Shift (EfES) algorithm for Electic Energy Storage (EES) analysis

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/AirborneKiwi/effective_energy_shift.git/HEAD?labpath=demo_notebook.ipynb)

This repository contains the code for the Effective Energy Shift (EfES) algorithm. 
The algorithm is described in "Effective Energy Shift algorithm for Electric Energy Storage analysis" by J. Fellerer, D. Scharrer, and R. German, submitted to Applied Energy, 2024.

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
import numpy as np
import effective_energy_shift as efes

# Define the input data
power_generation = np.array([2,3,2,4,3,1,0,0,2,5,6,2,1,0,1,2,3,2,0,0,4,4,4,2])
power_demand = np.array([1,4,1,2,1,2,4,5,0,1,3,1,2,2,1,1,2,3,4,5,2,1,5,1])
delta_time_step = 1.

# Run the algorithm
result = efes.perform_effective_energy_shift(power_generation, power_demand, delta_time_step)

# Print the result
print(result.analysis_results.capacity)
print(result.analysis_results.energy_additional)
print(result.analysis_results.self_sufficiency)
print(result.analysis_results.self_consumption)
```

## Interactive visualization
A more elaborate example can be found in the jupyter notebook [demo_notebook.ipynb](demo_notebook.ipynb), which can be launched using the "launch binder" badge above.
The interactive visualization available in it is shown below:

![interactive_visualization_in_demo_notebook.jpg](examples%2Finteractive_visualization_in_demo_notebook.jpg)

## Parameter variation
A parameter variation can be run by using the ```run_parameter_variation(...)``` function. 
All individual results will be stored in a subfolder and can be loaded indiviually using the ```efes_dataclasses.unpickle(path_to_file)``` function for further analysis.
The results can be visualized using the ```plot_parameter_variation(...)``` function. 
The applicability of the plots depends on the chosen parameters however.
An example is shown below:
![house_example_results.png](examples%2Fhouse_example_results%2Fhouse_example_results.png)

## License

The code is provided under the MIT license. If you use the code in your research, please cite the paper above.

## Contact

If you have any questions, please contact the authors of the paper via <jonathan.fellerer@fau.de>.

