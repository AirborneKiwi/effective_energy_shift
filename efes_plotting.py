import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.collections import LineCollection, PatchCollection
import matplotlib.cm as cm

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "Helvetica"
})

import numpy as np
import pandas as pd

import efes_dataclasses as efes_dc
import effective_energy_shift as efes
import math_energy_systems as mes

def plot_input(results: efes_dc.Results, final_callback=None, show=True):
    fig, axs = plt.subplots(3, 1, sharex=True, figsize=(15, 6))
    time = np.arange(0, results.analysis_results.data_input.delta_time_step * (1+len(results.analysis_results.data_input.power_residual_generation)), results.analysis_results.data_input.delta_time_step)

    # plot power generation
    y = np.array([*results.analysis_results.data_input.power_generation, results.analysis_results.data_input.power_generation[-1]])
    axs[0].step(x=time, y=y, where='post', color='green', label=r'$\mathit{P}_{\mathrm{gen}}$')
    axs[0].fill_between(x=time, y1=y, step='post',
                        facecolor='green', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{gen}}=$' + efes.pretty_print(results.analysis_results.energy_generation, 'Wh', decimals=0)
                        )

    # plot power used generation
    y = np.array([*results.analysis_results.data_input.power_used_generation, results.analysis_results.data_input.power_used_generation[-1]])
    axs[0].fill_between(x=time, y1=y, step='post',
                        facecolor='white', hatch='//////', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{ugen}}=$' + efes.pretty_print( results.analysis_results.energy_used_generation, 'Wh', decimals=0)
                        )

    # add legend with additional information on self-consumption
    lgd = axs[0].legend(bbox_to_anchor=(1.0, 1.0))
    handles, labels = axs[0].get_legend_handles_labels()
    handles.append(Patch(facecolor='w', edgecolor='w'))
    labels.append(r'$\psi_{\mathrm{sc}}=$' + f'{results.analysis_results.self_consumption_initial:.2f}')
    lgd._legend_box = None
    lgd._init_legend_box(handles, labels)
    lgd._set_loc(lgd._loc)
    lgd.set_title(lgd.get_title().get_text())

    # plot power demand
    y = np.array([*results.analysis_results.data_input.power_demand, results.analysis_results.data_input.power_demand[-1]])
    axs[1].step(x=time, y=y, where='post', color='red', label=r'$\mathit{P}_{\mathrm{dem}}$')
    axs[1].fill_between(x=time, y1=y, step='post',
                        facecolor='red', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{dem}}=$' + efes.pretty_print(results.analysis_results.energy_demand, 'Wh', decimals=0)
                        )

    # plot power covered demand
    y = np.array([*results.analysis_results.data_input.power_covered_demand, results.analysis_results.data_input.power_covered_demand[-1]])
    axs[1].fill_between(x=time, y1=y, step='post',
                        facecolor='white', hatch='//////', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{cdem}}=$' + efes.pretty_print( results.analysis_results.energy_covered_demand, 'Wh', decimals=0)
                        )

    # add legend with additional information on self-sufficiency
    lgd = axs[1].legend(bbox_to_anchor=(1.0, 1.0))
    handles, labels = axs[1].get_legend_handles_labels()
    handles.append(Patch(facecolor='w', edgecolor='w'))
    labels.append(r'$\psi_{\mathrm{ss}}=$' + f'{results.analysis_results.self_sufficiency_initial:.2f}')
    lgd._legend_box = None
    lgd._init_legend_box(handles, labels)
    lgd._set_loc(lgd._loc)
    lgd.set_title(lgd.get_title().get_text())

    # plot power residual generation
    y = np.array([*results.analysis_results.data_input.power_residual_generation, results.analysis_results.data_input.power_residual_generation[-1]])
    axs[2].step(x=time, y=y, where='post', color='black', label=r'$\mathit{P}_{\mathrm{rgen}}$')

    # plot power excess and deficit
    power_excess_initial = np.clip(y, a_min=0, a_max=np.inf)
    axs[2].fill_between(x=time, y1=power_excess_initial, step='post',
                        color='green', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{exs}}=$' + efes.pretty_print(power_excess_initial[:-1].sum() * results.analysis_results.data_input.delta_time_step, 'Wh', decimals=0)
                        )
    power_deficit_initial = np.clip(y, a_min=-np.inf, a_max=0)
    axs[2].fill_between(x=time, y1=power_deficit_initial, step='post', color='red', alpha=0.2,
                        label=r'$\mathit{E}_{\mathrm{def}}=$' + efes.pretty_print(-power_deficit_initial[:-1].sum() * results.analysis_results.data_input.delta_time_step, 'Wh', decimals=0)
                        )

   # add legend with additional information on maxmimum self-consumption and self-sufficiency
    lgd = axs[2].legend(bbox_to_anchor=(1.0, 1.0))
    handles, labels = axs[2].get_legend_handles_labels()
    handles.append(Patch(facecolor='w', edgecolor='w'))
    labels.append(r'$\psi_{\mathrm{sc,max}}=$' + f'{results.analysis_results.self_consumption_max:.2f}')
    handles.append(Patch(facecolor='w', edgecolor='w'))
    labels.append(r'$\psi_{\mathrm{ss,max}}=$' + f'{results.analysis_results.self_sufficiency_max:.2f}')
    lgd._legend_box = None
    lgd._init_legend_box(handles, labels)
    lgd._set_loc(lgd._loc)
    lgd.set_title(lgd.get_title().get_text())

    # set labels and grid
    axs[0].set(ylabel='Power [W]')
    axs[1].set(ylabel='Power [W]')
    axs[2].set(ylabel='Power [W]', xlabel='Time [h]', xlim=(time.min(), time.max()))
    axs[0].grid()
    axs[1].grid()
    axs[2].grid()
    fig.tight_layout()

    if final_callback is not None:
        fig, axs = final_callback(fig, axs)

    if show:
        plt.show()


def plot_energy_packets(current_step, phases, mask, efficiency_discharging, add_collect_plot=True, add_count_plot=True,
                        final_callback=None, show=True):
    # Create figure and axes
    cols = 1
    if add_collect_plot:
        cols = cols + 1
    if add_count_plot:
        cols = cols + 1

    fig, axs = plt.subplots(1, cols, figsize=(15, 4), width_ratios=(2, 1, 1), sharey=True)

    x = np.arange(len(phases))
    width = 0.25
    energy_packets_excess = []
    energy_packets_deficit = []
    energy_packets_deficit_covered = []

    linewidth_excess = []
    linewidth_deficit = []
    colors_excess = []
    colors_deficit = []
    colors_deficit_covered = []
    capacity_max = 0

    for n_phase, phase in enumerate(phases):
        energy_packets_excess.extend(
            [Rectangle(xy=(n_phase - width + 1, y), width=width, height=height) for (y, height) in zip(phase.starts_excess, phase.energy_excess)])
        energy_packets_deficit.extend([Rectangle(xy=(n_phase + 1, y), width=width, height=height) for (y, height) in zip(phase.starts_deficit, phase.energy_deficit)])
        energy_packets_deficit_covered.extend([Rectangle(xy=(n_phase, y), width=1, height=height) for (y, height, balanced) in zip(phase.starts_deficit, phase.energy_deficit, phase.deficit_balanced) if balanced])

        linewidth_excess.extend([(3 if balanced else 1) for balanced in phase.excess_balanced])
        linewidth_deficit.extend([(3 if balanced else 1) for balanced in phase.deficit_balanced])
        colors_excess.extend(phase.excess_ids)
        colors = np.full(len(phase.deficit_balanced), -1)
        colors[phase.deficit_balanced] = phase.excess_ids[phase.excess_balanced]
        colors_deficit.extend(colors)
        colors_deficit_covered.extend(colors[phase.deficit_balanced])

        capacity_max = max(capacity_max, (phase.starts_excess + phase.energy_excess).max(), (phase.starts_deficit + phase.energy_deficit).max())

    # Create patch collection with specified color/alpha
    norm = mpl.colors.Normalize(vmin=0, vmax=max(colors_excess))
    m = cm.ScalarMappable(norm=norm, cmap=cm.nipy_spectral)

    pc_excess = PatchCollection(energy_packets_excess, edgecolor='black', linewidths=linewidth_excess,
                                facecolors=[m.to_rgba(color_excess) for color_excess in colors_excess]
                                )
    pc_deficit = PatchCollection(energy_packets_deficit, edgecolor='black', linewidths=linewidth_deficit,
                                 facecolors=[(m.to_rgba(color_deficit) if color_deficit >= 0 else 'white') for color_deficit in colors_deficit]
                                 )
    pc_deficit_covered = PatchCollection(energy_packets_deficit_covered, edgecolor='black', linewidths=1,
                                         facecolors=[m.to_rgba(color_deficit) for color_deficit in colors_deficit_covered]
                                         )

    col = 0

    # Add collection to axes
    axs[col].add_collection(pc_excess)
    axs[col].add_collection(pc_deficit)
    axs[col].set(xlim=(0.5, x.max() + 1.5), ylim=(0, capacity_max * 1.1),
                 ylabel='Capacity [Wh]', xlabel='Phase [1]',
                 title=f'Energy packets after step {current_step}')
    axs[col].grid()

    if add_collect_plot:
        col = col + 1
        axs[col].add_collection(pc_deficit_covered)
        axs[col].set(xlim=(0, x.max() + 1.5), xlabel='Phase [1]', title=f'"Collect" results')
        axs[1].grid()

    if add_count_plot:
        col = col + 1
        count_results = efes.compute_battery_arrays_from_phases(phases, efficiency_discharging)
        axs[col].step(count_results['effectiveness_local'], count_results['capacity'])
        axs[col].set(xlim=(0, x.max() + 1.5), xlabel='Local effectiveness_local [1]', title=f'"Count" results')
        axs[col].grid()

    fig.tight_layout()

    if final_callback is not None:
        fig, axs = final_callback(fig, axs)

    if show:
        plt.show()


def run_query_for_continuous_plots(results: efes_dc.Results, capacity_min=None, capacity_max=None, resolution=500):
    if capacity_min is None:
        capacity_min = 0.001 * results.analysis_results.capacity[-1]
    if capacity_max is None:
        capacity_max = 1.5 * results.analysis_results.capacity[-1]

    return efes.run_dimensioning_query_for_target_capacity(results.analysis_results, capacity_target=np.linspace(capacity_min, capacity_max, resolution))

def add_effectiveness_plot_to_axes(ax, results:efes_dc.Results, query_results:efes_dc.QueryResults = None, use_fill=False, capacity_min=None, capacity_max=None, **kwargs):
    if query_results is None:
        query_results = run_query_for_continuous_plots(results, capacity_min, capacity_max)

    if not use_fill:
        ax.plot(query_results.capacity, query_results.effectiveness, label=r'effectiveness $\mu$', **kwargs)
    else:
        ax.fill_between(query_results.capacity, query_results.effectiveness, y2=0, **kwargs)

    return query_results

def add_gain_plot_to_axes(ax, results:efes_dc.Results, query_results:efes_dc.QueryResults = None, use_fill=False, capacity_min=None, capacity_max=None, **kwargs):
    if query_results is None:
        query_results = run_query_for_continuous_plots(results, capacity_min, capacity_max)

    if not use_fill:
        ax.plot(query_results.capacity, query_results.gain, label=r'gain $\mathit{G}$', **kwargs)
    else:
        ax.fill_between(query_results.capacity, query_results.gain, y2=0, **kwargs)

    return query_results

def add_gain_per_day_plot_to_axes(ax, results:efes_dc.Results, query_results:efes_dc.QueryResults = None, use_fill=False, capacity_min=None, capacity_max=None, **kwargs):
    if query_results is None:
        query_results = run_query_for_continuous_plots(results, capacity_min, capacity_max)

    if not use_fill:
        ax.plot(query_results.capacity, query_results.gain_per_day, label=r'gain $\mathit{G}_{\mathrm{day}}$', **kwargs)
    else:
        ax.fill_between(query_results.capacity, query_results.gain_per_day, y2=0, **kwargs)
    return query_results

def add_local_effectiveness_plot_to_axes(ax, results:efes_dc.Results, use_fill=False, **kwargs):
    x = results.analysis_results.capacity
    x = np.append(x, x[-1] * 100)
    if not use_fill:
        ax.step(x, [*results.analysis_results.effectiveness_local, 0], where='post', label=r'local effectiveness $\mathit{m}$', **kwargs)
    else:
        ax.fill_between(x, [*results.analysis_results.effectiveness_local, 0], y2=0, step='post', **kwargs)


def add_secondary_axis(axs, xlim_primary, ylim_primary, secondary_limits, primary_to_secondary_func, secondary_to_primary_func, axes_x, axes_title, tick_width=0.002, label_offset=0.001, label_lim_offset=0.005):

    # calculate secondary limits in primary scale
    secondary_limits_in_primary = secondary_to_primary_func(np.array(secondary_limits))
    # if secondary limits are out of primary limits, clip them
    lower_limit_out_of_axes = secondary_limits_in_primary[0] < ylim_primary[0]
    upper_limit_out_of_axes = secondary_limits_in_primary[1] > ylim_primary[1]

    secondary_limits_in_primary = np.clip(secondary_limits_in_primary, ylim_primary[0], ylim_primary[1])
    primary_limits_in_secondary = primary_to_secondary_func(np.array(ylim_primary))

    # add vertical lines for secondary axes
    line = Line2D([xlim_primary[1] * axes_x, xlim_primary[1] * axes_x], secondary_limits_in_primary, lw=1., color='black')
    line.set_clip_on(False)
    axs.add_artist(line)

    # add ticks for secondary axes
    tick_limits = [max(secondary_limits[0], primary_limits_in_secondary[0]), min(secondary_limits[1], primary_limits_in_secondary[1])]

    scale, _ = efes.get_scaling(tick_limits[1])
    def get_tick_option(relative_tick_step):
        return np.arange(np.round(tick_limits[0] / relative_tick_step) * relative_tick_step, np.round(tick_limits[1] / relative_tick_step) * relative_tick_step + relative_tick_step / scale, relative_tick_step/scale)

    tick_options = [get_tick_option(relative_tick_step) for relative_tick_step in [0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5]]
    target_tick_count = 6
    tick_diff_to_target = np.abs(np.array([len(tick_option) for tick_option in tick_options]) - target_tick_count)
    ticks = tick_options[np.argmin(tick_diff_to_target)]

    ticks = ticks[(ticks >= tick_limits[0] + 0.02 * tick_limits[1]) & (ticks <= 0.98 * tick_limits[1])]

    ticks_loc = secondary_to_primary_func(ticks)
    ticks_loc = ticks_loc[(ticks_loc >= ylim_primary[0]) & (ticks_loc <= ylim_primary[1])]
    lc_ticks = LineCollection(
        segments=[((xlim_primary[1] * (axes_x - tick_width), loc), (xlim_primary[1] * (axes_x + tick_width), loc)) for
                  loc in ticks_loc],
        linewidth=1,
        clip_on=False,
        color='black'
    )
    axs.add_artist(lc_ticks)

    # add labels for secondary ticks
    for loc, label in zip(ticks_loc, ticks):
        axs.add_artist(Text(
            x=xlim_primary[1] * (axes_x + tick_width + label_offset),
            y=loc, text=f'{np.round(label/scale,3)*scale}',
            clip_on=False,
            verticalalignment='center')
        )

    # add thicker ticks for secondary limits, if not outside axes
    if not lower_limit_out_of_axes:
        axs.add_artist(Line2D([xlim_primary[1] * (axes_x - 2 * tick_width), xlim_primary[1] * (axes_x + 2 * tick_width)], [secondary_limits_in_primary[0], secondary_limits_in_primary[0]], lw=2., color='black', clip_on=False))

    if not upper_limit_out_of_axes:
        axs.add_artist(Line2D([xlim_primary[1] * (axes_x - 2 * tick_width), xlim_primary[1] * (axes_x + 2 * tick_width)], [secondary_limits_in_primary[1], secondary_limits_in_primary[1]], lw=2., color='black', clip_on=False))

    # add labels for secondary limits
    if not lower_limit_out_of_axes:
        axs.add_artist(Text(
            x=xlim_primary[1] * (axes_x + tick_width + label_lim_offset),
            y=secondary_limits_in_primary[0],
            text=f'{np.round(secondary_limits[0]*scale, 3)/scale}',
            clip_on=False,
            verticalalignment='center')
        )
    if not upper_limit_out_of_axes:
        axs.add_artist(Text(
            x=xlim_primary[1] * (axes_x + tick_width + label_lim_offset),
            y=secondary_limits_in_primary[1],
            text=f'{np.round(secondary_limits[-1]*scale, 3)/scale}',
            clip_on=False,
            verticalalignment='center')
        )

    # add title for secondary axes
    axs.add_artist(Text(
        x=xlim_primary[1] * axes_x, y=1.1 * secondary_limits_in_primary[1],
        text=axes_title,
        clip_on=False,
        horizontalalignment='left',
        verticalalignment='bottom')
    )


def plot_results(results: efes_dc.Results,
                 add_self_sufficiency_axes=True,
                 add_self_consumption_axes=True,
                 add_gain_plot=True,
                 query_kwargs = {},
                 n_additional_plots=0,
                 xlim=None,
                 ylims=None,
                 figsize=None,
                 final_callback=None,
                 show=True
                 ):

    rows = 2 if add_gain_plot else 1
    rows = rows + n_additional_plots

    if figsize is None:
        figsize = (15, 3 * rows)

    fig, axs = plt.subplots(rows, 1, sharex=True, figsize=figsize)
    if rows == 1:
        axs = [axs]

    x = results.analysis_results.capacity
    x = np.append(x, x[-1] * 1.5)

    if xlim is None:
        xlim = (x.min(), x.max())

    y = [*results.analysis_results.energy_additional, results.analysis_results.energy_additional[-1]]

    if ylims is None:
        ylims = [None] * rows

    query_results_limits = efes.run_dimensioning_query_for_target_capacity(results.analysis_results, capacity_target=np.array(xlim))

    if ylims[0] is None:
        ylims[0] = [0, 1.2*query_results_limits.energy_additional[1]]

    axs[0].plot(x, y, color='black', linewidth=1)
    max_out_of_bounds = results.analysis_results.energy_additional[-1] >= ylims[0][1]
    if not max_out_of_bounds:
        axs[0].axhline(y=results.analysis_results.energy_additional[-1],
                       linestyle='--',
                       color='black',
                       linewidth=1
                       )

    axs[0].add_artist(mpl.text.Text(
        x=xlim[0] + 0.03 * xlim[1],
        y=1.01 * results.analysis_results.energy_additional[-1] if not max_out_of_bounds else 0.97 * ylims[0][1],
        text=f'Max: {efes.pretty_print(results.analysis_results.energy_additional[-1], "Wh")}',
        clip_on=False,
        horizontalalignment='left',
        verticalalignment='bottom' if not max_out_of_bounds else 'top'
    ))

    axes_x = 1.01
    if add_self_sufficiency_axes:
        def primary_to_secondary_func(ticks):
            return mes.calculate_self_sufficiency_from_additional_energy(energy_additional=ticks,
                                                                         energy_demand=results.analysis_results.energy_demand,
                                                                         self_sufficiency_initial=results.analysis_results.self_sufficiency[0]
                                                                         )
        def secondary_to_primary_func(ticks):
            return mes.calculate_additional_energy_from_self_sufficiency(self_sufficiency=ticks,
                                                                         energy_demand=results.analysis_results.energy_demand,
                                                                         self_sufficiency_initial=results.analysis_results.self_sufficiency[0]
                                                                         )

        add_secondary_axis(axs[0],
                           xlim_primary=xlim,
                           ylim_primary=ylims[0],
                           secondary_limits=[results.analysis_results.self_sufficiency[0], results.analysis_results.self_sufficiency[-1]],
                           primary_to_secondary_func=primary_to_secondary_func,
                           secondary_to_primary_func=secondary_to_primary_func,
                           axes_x=axes_x,
                           axes_title=r'$\psi_{\mathrm{ss}}$',
                           )

        axes_x = axes_x + 0.06

    if add_self_consumption_axes:

        def primary_to_secondary_func(ticks):
            return mes.calculate_self_consumption_from_additional_energy(energy_additional=ticks,
                                                                         energy_generation=results.analysis_results.energy_generation,
                                                                         self_consumption_initial=
                                                                         results.analysis_results.self_consumption[0],
                                                                         efficiency_discharging=results.analysis_results.data_input.efficiency_discharging,
                                                                         efficiency_charging=results.analysis_results.data_input.efficiency_charging
                                                                         )
        def secondary_to_primary_func(ticks):
            return mes.calculate_additional_energy_from_self_consumption(self_consumption=ticks,
                                                                         energy_generation=results.analysis_results.energy_generation,
                                                                         self_consumption_initial= results.analysis_results.self_consumption[0],
                                                                         efficiency_discharging=results.analysis_results.data_input.efficiency_discharging,
                                                                         efficiency_charging=results.analysis_results.data_input.efficiency_charging
                                                                         )

        add_secondary_axis(axs[0],
                           xlim_primary=xlim,
                           ylim_primary=ylims[0],
                           secondary_limits=[results.analysis_results.self_consumption[0],
                                             results.analysis_results.self_consumption[-1]],
                           primary_to_secondary_func=primary_to_secondary_func,
                           secondary_to_primary_func=secondary_to_primary_func,
                           axes_x=axes_x,
                           axes_title=r'$\psi_{\mathrm{sc}}$',
                           )


    axs[0].grid()
    axs[0].set(ylabel=r'$\mathit{E}^{+}$ [Wh]', ylim=ylims[0])

    if add_gain_plot:
        query_result = add_effectiveness_plot_to_axes(axs[1], results, **query_kwargs)

        add_gain_plot_to_axes(axs[1], results, query_result, linewidth=2, linestyle='--')
        add_local_effectiveness_plot_to_axes(axs[1], results)

        axs[1].legend()

        axs[1].grid()
        axs[1].set(ylabel=r'$\mathit{G}$, $\mu$ and $\mathit{m}$ [1]', ylim=ylims[1])

    axs[-1].set(xlabel=r'$C$ [Wh]', xlim=xlim)
    fig.tight_layout()

    if final_callback is not None:
        fig, axs = final_callback(fig, axs)

    if show:
        plt.show()


def create_variation_plot(parameter_study_results: efes_dc.ParameterStudyResults,
                          cmap_parameter_name=None,
                          cbar_label='',
                          index_reference_result=-1,
                          use_fill=True,
                          cmap_name='jet',
                          add_self_sufficiency_axes=True,
                          add_self_consumption_axes=True,
                          add_local_effectiveness_plot=True,
                          add_effectiveness_plot=True,
                          add_gain_axes=True,
                          add_gain_per_day_axes=True,
                          xlim=None,
                          ylims=None,
                          figsize=None,
                          final_callback=None,
                          show=True,
                          ):
    if cmap_parameter_name is None:
        cmap_parameter_name = parameter_study_results.parameter_variation.columns[0]

    if cbar_label == '':
        cbar_label = cmap_parameter_name


    vmin = parameter_study_results.parameter_variation[cmap_parameter_name].replace([np.inf, -np.inf], np.nan).dropna().min()
    vmax = parameter_study_results.parameter_variation[cmap_parameter_name].replace([np.inf, -np.inf], np.nan).dropna().max()

    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    m = cm.ScalarMappable(norm=norm, cmap=mpl.colormaps[cmap_name])

    reference_result = parameter_study_results.results[index_reference_result]
    reference_result_needs_loading = isinstance(reference_result, str)
    if reference_result_needs_loading:
        reference_result = efes_dc.unpickle(reference_result)

    def add_paramter_variation_results(fig, axs):
        xlim = axs[0].get_xlim()

        query_results_limits = efes.run_dimensioning_query_for_target_capacity(reference_result.analysis_results,
                                                                               capacity_target=np.array([xlim[0] + 0.001 * xlim[1], xlim[1]]))

        xlabel = axs[-1].get_xlabel()
        if len(axs) > 1:
            axs[1].clear()  # clear axes content, since not all results can be visualized at the same time


        cbar = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=mpl.colormaps[cmap_name]),
                            ax=axs[0],
                            location='top',
                            anchor=(1.0, 0.),
                            shrink=0.5,
                            extend='both'
                            )

        cbar.ax.set_xlabel(xlabel=cbar_label)#, labelpad=15)

        for variation, results in zip(parameter_study_results.parameter_variation.to_dict(orient='records')[::-1],
                                      parameter_study_results.results[::-1]):
            results_needs_loading = isinstance(results, str)
            if results_needs_loading:
                results = efes_dc.unpickle(results)

            color = m.to_rgba(variation[cmap_parameter_name])
            query_variation_results_limits = efes.run_dimensioning_query_for_target_capacity(results.analysis_results,
                                                                                   capacity_target=np.array( [xlim[0] + 0.001 * xlim[1], xlim[1]]))
            capacity = results.analysis_results.capacity[(results.analysis_results.capacity > xlim[0]) & (results.analysis_results.capacity < xlim[1])]
            energy_additional = results.analysis_results.energy_additional[ (results.analysis_results.capacity > xlim[0]) & (results.analysis_results.capacity < xlim[1])]

            if use_fill:
                axs[0].fill_between([query_variation_results_limits.capacity[0], *capacity, query_variation_results_limits.capacity[1]], [query_variation_results_limits.energy_additional[0], *energy_additional, query_variation_results_limits.energy_additional[-1]], y2=0,
                                    color=color)
            else:
                axs[0].plot([query_variation_results_limits.capacity[0], *capacity, query_variation_results_limits.capacity[1]], [query_variation_results_limits.energy_additional[0], *energy_additional, query_variation_results_limits.energy_additional[-1]], linestyle='-',
                            linewidth=2, color=color)

            row = 1
            if add_local_effectiveness_plot:
                add_local_effectiveness_plot_to_axes(axs[row], results, use_fill=use_fill, color=color)
                row = row + 1

            add_effectiveness_plot_to_axes(axs[row], results,
                                           capacity_min=xlim[0] + 0.001 * xlim[1],
                                           capacity_max=xlim[1],
                                           use_fill=use_fill,
                                           color=color
                                           )

            if results_needs_loading:
                del results

        row = 1
        if add_local_effectiveness_plot:
            add_local_effectiveness_plot_to_axes(axs[row], reference_result, color='black')
            axs[row].set(ylabel=r'$\mathit{m}$ [1]')
            if ylims[row] is None:
                ylims[row] = [0, 1.2*query_results_limits.effectiveness_local.max()]

            axs[row].set(ylim=ylims[row])
            axs[row].grid()
            row = row + 1


        query_results = add_effectiveness_plot_to_axes(axs[row], reference_result,
                                                       capacity_min=0.001 * xlim[-1],
                                                       capacity_max=xlim[1],
                                                       linestyle='-', linewidth=2, color='black'
                                                       )
        if ylims[row] is None:
            ylims[row] = [0, 1.2*query_results_limits.effectiveness.max()]

        axs[row].set(ylim=ylims[row])
        axs[row].set(ylabel=r'$\mu$ [1]')
        axs[row].grid()

        axes_x = 1.01
        if add_gain_axes:
            def primary_to_secondary_func(ticks):
                return mes.calculate_gain_from_effectiveness(effectiveness=ticks, efficiency_discharging=reference_result.analysis_results.data_input.efficiency_discharging)

            def secondary_to_primary_func(ticks):
                return mes.calculate_effectiveness_from_gain(gain=ticks, efficiency_discharging=reference_result.analysis_results.data_input.efficiency_discharging)

            add_secondary_axis(axs[row],
                               xlim_primary=xlim,
                               ylim_primary=ylims[row],
                               secondary_limits=[0, query_results.gain.max()],
                               primary_to_secondary_func=primary_to_secondary_func,
                               secondary_to_primary_func=secondary_to_primary_func,
                               axes_x=axes_x,
                               axes_title=r'$\mathit{G}$',
                               )

            axes_x = axes_x + 0.06

        if add_gain_per_day_axes:

            def primary_to_secondary_func(ticks):
                return mes.calculate_gain_per_day_from_effectiveness(effectiveness=ticks, time_total=reference_result.analysis_results.time_total, efficiency_discharging=reference_result.analysis_results.data_input.efficiency_discharging)

            def secondary_to_primary_func(ticks):
                return mes.calculate_effectiveness_from_gain_per_day(gain_per_day=ticks, time_total=reference_result.analysis_results.time_total, efficiency_discharging=reference_result.analysis_results.data_input.efficiency_discharging)

            add_secondary_axis(axs[row],
                               xlim_primary=xlim,
                               ylim_primary=ylims[row],
                               secondary_limits=[0, query_results.gain_per_day.max()],
                               primary_to_secondary_func=primary_to_secondary_func,
                               secondary_to_primary_func=secondary_to_primary_func,
                               axes_x=axes_x,
                               axes_title=r'$\mathit{G}_{\mathrm{day}}$',
                               )

        axs[-1].set(xlabel=xlabel)

        if final_callback is not None:
            fig, axs = final_callback(fig, axs)

        return fig, axs

    n_additional_plots = 1 if add_local_effectiveness_plot else 0

    # since the follwoing plots can be handled with a secondary y-axis, we only need to add a single additional plot
    if add_effectiveness_plot:
        n_additional_plots += 1

    if ylims is None:
        ylims = [None] * (n_additional_plots+1)
    elif len(ylims) < n_additional_plots+1:
        ylims = [*ylims, *([None]*(n_additional_plots+1-len(ylims)))]

    if figsize is None:
        figsize = (15, 3 + n_additional_plots * 2)

    plot_results(reference_result,
                          add_self_sufficiency_axes=add_self_sufficiency_axes,
                          add_self_consumption_axes=add_self_consumption_axes,
                          add_gain_plot=n_additional_plots > 0,
                          n_additional_plots=max(0, n_additional_plots-1),
                          figsize=figsize,
                          xlim=xlim,
                          ylims=ylims,
                          final_callback=add_paramter_variation_results,
                          show=show
                          )

    if reference_result_needs_loading:
        del reference_result_needs_loading