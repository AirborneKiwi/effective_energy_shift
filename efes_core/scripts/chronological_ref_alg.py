import numpy as np

def run_chronological_algorithm(
        power_generation,
        power_demand,
        delta_time_step,
        capacity,
        charge_initial = 0,
        power_max_charging = np.inf,
        power_max_discharging = np.inf,
        efficiency_charging = 1.0,
        efficiency_discharging = 1.0,
        efficiency_direct_usage = 1.0,
        **kwargs
    ):
    # initialize
    N_timesteps = len(power_generation)
    energy_additional_over_time = np.zeros(N_timesteps)
    if capacity <= 0:
        return energy_additional_over_time

    charge = charge_initial
    charge_prev = np.full(N_timesteps, -1, dtype='float')  # sentinel

    
    k = 0 
    i = 0
    varepsilon_abs = 1e-10 
    varepsilon_rel = 1e-8
    
    while abs(charge - charge_prev[k]) > varepsilon_abs + varepsilon_rel * max( 1, abs(charge), abs(charge_prev[k])):
        charge_prev[k] = charge
        
        power_used_generation = min( power_demand[k] / efficiency_direct_usage, power_generation[k] )
        power_residual = power_generation[k] - power_demand[k] - power_used_generation * (1-efficiency_direct_usage)    

        if power_residual > 0:  # surplus (charging)
            delta = min( power_residual * delta_time_step, power_max_charging * delta_time_step, (capacity - charge)/efficiency_charging )
            charge = charge + efficiency_charging * delta
            energy_additional_over_time[k] = 0
        else:  # deficit (discharging)
            delta = min( -power_residual * delta_time_step, power_max_discharging * delta_time_step, charge * efficiency_discharging )
            charge = charge - delta  / efficiency_discharging
            energy_additional_over_time[k] = delta
    
        k = (k + 1) % N_timesteps
        i = i + 1

    return energy_additional_over_time


def query_capacities(capacity_target, **kwargs):
    import pandas as pd

    df = pd.DataFrame(data={'capacity': capacity_target, 'energy_additional_chrono': [None]*len(capacity_target)})

    def calc_energy_additional(s):
        energy_additional_over_time = run_chronological_algorithm(
            capacity=s['capacity'],
            **kwargs
        )
        return sum(energy_additional_over_time)
    df['energy_additional_chrono'] = df.apply(calc_energy_additional, axis=1)
    return df
        

if __name__ == '__main__':
    power_generation = np.array([2,3,2,4,3,1,0,0,2,5,6,2,1,0,1,2,3,2,0,0,4,4,4,2])
    power_demand = np.array([1,4,1,2,1,2,4,5,0,1,3,1,2,2,1,1,2,3,4,5,2,1,5,1])
    delta_time_step = 1.0

    capacities = [-1, 0, 1, 2, 3, 4, 5, 6, 10, 15]
    
    query_capacities(
        capacities=capacities,
        power_generation=power_generation,
        power_demand=power_demand,
        delta_time_step=delta_time_step,
    )