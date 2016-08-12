# Core imports
import glob
import os
import re
import shutil
import sys
import traceback
from collections import OrderedDict

# Library imports
import numpy as np

# matplotlib imports
import matplotlib
try:
    matplotlib.use('Agg')
except ValueError as e:
    raise ImportError("Could not load matplotlib backend: {}".format(e.message))
finally:
    import matplotlib.pyplot as plt

# Package imports
from __init__ import __package__
from planning.Algorithm import NSGA, SMS_EMOA
from planning.Experiment import Experiment
from planning.Problem import Reconstruction_Plan_Discrete
from settings import Arguments

class Experiment_Results(Experiment):
    def __init__(self, arguments):
        super(Experiment_Results, self).__init__(arguments)

        self._settings = arguments.get_settings("planning_results")
        self._number_of_processes = self._settings.get("number_of_processes")

        self._overrides_in_dirs = self._settings.get("overrides_in_dirs")
        self._results_path = self._settings.get("results_path")
        if self._results_path.endswith("/"):
            self._results_path = self._results_path[:-1]

        if self._settings.get("singular"):
            # Flatten the experiments
            experiments = []
            for experiment in self._experiments:
                for setting_key, options in experiment.iteritems():
                    experiments.append({setting_key: options})

            self._experiments = experiments

        problem = Reconstruction_Plan_Discrete(arguments)
        self._objectives = problem.get_objective_names()

        self._algorithms = [
            algorithm(problem, arguments) for algorithm in (NSGA, SMS_EMOA)
        ]

        objectives_parts = ["([0-9.-]+)"] * len(self._objectives)
        objectives_regex = r"\s*{}\s*".format(r",?\s+".join(objectives_parts))

        # Regular expression patterns that can parse output logs from runs.
        # - "regex" is a regular expression containing some numbered groups.
        # - "names" is a sequence of descriptive names for the data matched by
        #   the groups in "regex".
        # - "casts" is a sequence of types that cast the data from the groups
        #   to appropriate types.
        # - "group" specifies the data group the matched line is part of.
        #   If the group name exists within the "names", then the matched data 
        #   is used as an identifier within the resulting data.
        self._log_patterns = {
            "iteration": {
                "regex": r"^Iteration (\d+) \(([0-9.e-]+) sec, " + \
                         r"([0-9.e-]+) it/s\)",
                "names": ["iteration", "runtime", "speed"],
                "casts": [int, float, float],
                "group": "iteration"
            },
            "infeasible": {
                "regex": r"^Infeasible count: (\d+)",
                "names": ["infeasible"],
                "casts": [int],
                "group": "iteration"
            },
            "knees": {
                "regex": r"^Current knee point objectives: " + \
                         r"\[{}\]".format(objectives_regex),
                "names": self._objectives,
                "casts": [float] * len(self._objectives),
                "group": "iteration"
            },
            "individual": {
                "regex": r"^(\d+)\. \[{}\] \((\d+)\)".format(objectives_regex),
                "names": ["individual"] + self._objectives + ["unsnappable"],
                "casts": [int] + [float] * len(self._objectives) + [int],
                "group": "individual"
            },
            "individual_plot": {
                "regex": r"^Saved plot as (.+)",
                "names": ["plot_file"],
                "casts": [str],
                "group": "individual"
            },
            "pareto": {
                "regex": r"^Pareto front after t=(\d+)",
                "names": ["iteration"],
                "casts": [int],
                "group": "iteration"
            },
            "pareto_plot": {
                "regex": r"^Saved plot as (.+)",
                "names": ["plot_file"],
                "casts": [str],
                "group": "iteration"
            }
        }

        for pattern in self._log_patterns.itervalues():
            pattern["regex"] = re.compile(pattern["regex"])

        self._errors = 0
        self._total = 0

        # Settings that directly alter the objectives
        experiment_groups = [
            "collision_avoidance", "unsafe_path_cost", "delta_rate", "*"
        ]
        self._experiment_groups = set(experiment_groups)
        self._experiment_results = OrderedDict([
            (group, OrderedDict()) for group in experiment_groups
        ])

    def _error(self, message):
        sys.stderr.write("{}\n".format(message))
        self._errors += 1

    @property
    def failed(self):
        return self._errors

    def execute(self):
        for experiment in self._experiments:
            try:
                setting_keys, combinations = self.get_options(experiment)

                for combination in combinations:
                    self._run(setting_keys, combination)
            except ValueError as e:
                traceback.print_exc()
                self._error(e.message)

        self._output()

    def show_results(self):
        dir_count = len(glob.glob("{}/*/".format(self._results_path)))
        print("------------------------------")
        print("Number of experiments: {}".format(self._total))
        print("Number of directories containing results: {}".format(dir_count))
        print("Number of problems: {}".format(self._errors))

    def _format_dir_args(self, setting_keys, combination):
        formatted_args = self.format_args(setting_keys, combination)
        if self._overrides_in_dirs:
            formatted_args = self._settings_overrides + formatted_args

        return "-".join(formatted_args)

    def _run(self, setting_keys, combination):
        args = self._format_dir_args(setting_keys, combination)
        process_results = []
        for i in range(self._number_of_processes):
            self._total += 1
            path = "{}/{}-{}".format(self._results_path, args, i)
            if not os.path.exists(path):
                self._error("Missing results for {} process #{}".format(args, i))
                continue

            data = {}
            self._parse_output_log(path, data)
            self._calculate(data)

            process_results.append(data)

        total_results = self._sample(process_results)
        if total_results:
            self._record(setting_keys, combination, args, total_results)

    def _parse_output_log(self, path, data):
        current = {
            "iteration": -1,
            "individual": -1
        }
        current_group = None
        data["iteration"] = OrderedDict()
        data["individual"] = OrderedDict()
        with open("{}/output.log".format(path), "r") as output_log:
            for line in output_log:
                for pattern in self._log_patterns.itervalues():
                    if current_group != pattern["group"]:
                        if not self._is_grouping(pattern):
                            continue

                    matches = pattern["regex"].match(line)
                    if matches:
                        values = self._cast(pattern["casts"], matches.groups())
                        groups = dict(zip(pattern["names"], values))
                        current_group = pattern["group"]
                        if self._is_grouping(pattern):
                            current[current_group] = groups[current_group]
                            del groups[current_group]

                        identifier = current[current_group]
                        if identifier not in data[current_group]:
                            data[current_group][identifier] = {}

                        data[current_group][identifier].update(groups)

    def _is_grouping(self, pattern):
        return pattern["group"] in pattern["names"]

    def _cast(self, casts, values):
        return [cast(value) for cast, value in zip(casts, values)]

    def _calculate(self, data):
        # What do we want:
        # - bar charts or other plots of comparisons between combinations of
        #   one experiment, using (average) knee point values?
        # - convergence plots
        # - "interesting" pareto fronts or spreading measures, etc.
        # - "best" result (take into account that objective values differ
        #   between parameters, so we need to compare within isometric groups.)
        its = data["iteration"]
        ins = data["individual"]

        knees = OrderedDict()
        for it in its:
            if self._objectives[0] not in its[it]:
                knees[it] = np.array([np.inf] * len(self._objectives))
            else:
                knees[it] = np.array([its[it][obj] for obj in self._objectives])

        iteration_limit = max(its.keys())
        data["results"] = {
            "knees": knees,
            "knee": knees[iteration_limit]
        }
        for it_field in ("runtime", "speed"):
            data["results"][it_field] = OrderedDict([
                (iteration, its[iteration][it_field]) for iteration in its
            ])


        individuals = OrderedDict()
        for individual in ins:
            individuals[individual] = np.array([
                ins[individual][obj] for obj in self._objectives
            ])

        data["individuals"] = individuals

        data["results"]["contribution"] = np.empty(len(self._algorithms))
        for i, algorithm in enumerate(self._algorithms):
            if len(individuals) == 0:
                contribution = np.inf
            else:
                contribution = algorithm.sort_contribution(individuals)

            data["results"]["contribution"][i] = np.median(contribution)

    def _sample(self, process_results):
        # sample results from multiple processes (mean/median, std dev, var)
        if len(process_results) == 0:
            return {}

        total_results = {
            "processes": process_results
        }
        keys = process_results[0]["results"].keys()
        for key in keys:
            results = [data["results"][key] for data in process_results]
            if isinstance(results[0], OrderedDict):
                total = OrderedDict()
                for point in results[0]:
                    point_results = [result[point] for result in results]
                    total[point] = self._get_samples(point_results)

                total_results[key] = total
            else:
                total_results[key] = self._get_samples(results)

        return total_results

    def _get_samples(self, results):
        M = np.array(results)
        if len(M.shape) > 1 and M.shape[1] == 2:
            # Row-wise samples for 2d-arrays
            # Use Algorithm.sort_nondominated to retrieve pareto front and 
            # deduce a sampled minimum/maximum/knee from that.
            R = self._algorithms[0].sort_nondominated(M, all_layers=False)[0]
            M = np.array(R.values())
            samples = {}

            knee_idx = M.shape[0]/2
            keys = R.keys()
            samples["knee"] = M[knee_idx, :]
            samples["argknee"] = keys[knee_idx]

            sample_objectives = {
                "{}": np.min,
                "{}_max": np.max,
                "{}_std": np.std,
                "{}_knee": lambda column: column[knee_idx]
            }

            for i, obj in enumerate(self._objectives):
                for sample_format, func in sample_objectives.iteritems():
                    sample_key = sample_format.format(obj)
                    if np.any(M[:, i] == np.inf):
                        samples[sample_key] = np.inf
                    else:
                        samples[sample_key] = func(M[:, i])

            return samples

        sample_funcs = {
            "mean": np.mean,
            "std": np.std,
            "median": np.median,
            "min": np.amin,
            "max": np.amax,
            "var": np.var,
            "argmin": np.argmin
        }

        if np.any(M == np.inf):
            return dict([(key, np.inf) for key in sample_funcs])

        return dict([
            (key, func(M, axis=0)) for key, func in sample_funcs.iteritems()
        ])

    def _record(self, setting_keys, combination, args, experiment_results):
        experiment_results["settings"] = zip(setting_keys, combination)
        experiment_groups = self._experiment_groups.intersection(setting_keys)
        if experiment_groups:
            for group in experiment_groups:
                self._experiment_results[group][args] = experiment_results
        else:
            self._experiment_results["*"][args] = experiment_results

        if setting_keys not in self._experiment_results:
            self._experiment_results[setting_keys] = OrderedDict()

        self._experiment_results[setting_keys][args] = experiment_results

    def _output(self):
        for group, experiments in self._experiment_results.iteritems():
            self._find_best_knee(group, experiments)
            self._find_best_front(group, experiments)

            if group != "*":
                self._plot_iteration(group, experiments, "runtime")
                self._plot_iteration(group, experiments, "speed")
                for objective in self._objectives:
                    self._plot_iteration(group, experiments, "knees",
                                         mean="{}_knee".format(objective),
                                         std="{}_std".format(objective),
                                         name="{} at knee".format(objective))
                    self._plot_knee(group, experiments, objective)

    def _get_group_name(self, group, separator=", "):
        if isinstance(group, tuple):
            return separator.join(group)

        return group

    def _copy_plot_file(self, name, settings=None, plot_file=None,
                        process_id=None, **kwargs):
        args = self._format_dir_args(*zip(*settings))

        # If the experiment results were moved, then replace the old save path 
        # with the current results path
        plot_file = re.sub(r"^(.+)/({}-{})/(.+)$".format(args, process_id),
                           r"{}/\2/\3".format(self._results_path),
                           plot_file)
        if not os.path.exists(plot_file):
            self._error("Could not find plot file '{}' for {} to be copied to {}".format(plot_file, args, name))
            return

        extension = os.path.splitext(plot_file)[1]
        target_file = "{}/{}{}".format(self._results_path, name, extension)
        shutil.copyfile(plot_file, target_file)
        print("Copied {} to {}".format(plot_file, target_file))

    def _find_best(self, experiments, size, comparator, collector):
        best = np.array([np.inf] * size)
        best_data = {}
        for experiment in experiments.itervalues():
            value = comparator(experiment)
            if np.all(value < best):
                best = value
                best_data = collector(experiment, value)

        return best, best_data

    def _find_best_knee(self, group, experiments):
        comparator = lambda experiment: experiment["knee"]["knee"]
        best_knee, data = self._find_best(experiments, len(self._objectives),
                                          comparator, self._find_knee_plot)

        if not data:
            print("No best knee for '{}' found!".format(group))
            return

        print("Best knee for '{}': {}".format(group, best_knee))
        print("Settings: {}".format(" ".join(self._format_label_args(data))))
        group_key = self._get_group_name(group, separator="-")
        self._copy_plot_file("{}-best-knee".format(group_key), **data)

    def _find_knee_plot(self, experiment, knee):
        process_id = experiment["knee"]["argknee"]
        process = experiment["processes"][process_id]
        individual = self._find_individual(process, knee)

        return {
            "plot_file": individual["plot_file"],
            "process_id": process_id,
            "settings": experiment["settings"]
        }

    def _find_individual(self, data, knee):
        individuals = np.array(data["individuals"].values())
        close_individuals = np.isclose(individuals, knee, rtol=0.0)
        indexes = np.where(np.all(close_individuals, axis=1))[0]
        if len(indexes) == 0:
            raise ValueError("Could not find individual with objectives {} within population {}".format(knee, individuals))

        index = indexes[0]
        keys = data["individuals"].keys()
        individual_id = keys[index]

        return data["individual"][individual_id]

    def _find_best_front(self, group, experiments):
        comparator = lambda experiment: experiment["contribution"]["knee"]

        contribution, data = self._find_best(experiments, len(self._algorithms),
                                             comparator, self._find_front_plot)

        if not data:
            print("No best front for '{}' found!".format(group))
            return

        print("Best contribution for '{}': {}".format(group, contribution))
        print("Settings: {}".format(" ".join(self._format_label_args(data))))
        group_key = self._get_group_name(group, separator="-")
        self._copy_plot_file("{}-best-front".format(group_key), **data)

    def _find_front_plot(self, experiment, value):
        process_id = experiment["contribution"]["argknee"]
        process = experiment["processes"][process_id]
        iteration_limit = max(process["iteration"].keys())

        return {
            "plot_file": process["iteration"][iteration_limit]["plot_file"],
            "process_id": process_id,
            "settings": experiment["settings"]
        }

    def _start_plot(self, title, xlabel, ylabel):
        axes = plt.gca()
        axes.cla()
        axes.set_title(title)
        axes.set_xlabel(xlabel)
        axes.set_ylabel(ylabel)

    def _format_label_args(self, experiment, use_keys=True):
        args = []
        for key, value in experiment["settings"]:
            arg = self.format_arg(key, value)
            args.append(" ".join(arg if use_keys else arg[1:]))

        return args

    def _plot_iteration(self, group, experiments, key, mean="mean", std="std",
                        name=None):
        if name is None:
            name = key

        group_name = self._get_group_name(group)
        title = "Convergence of {} within {} group".format(name, group_name)
        self._start_plot(title, "iteration", key)

        axes = plt.gca()
        for experiment in experiments.itervalues():
            results = experiment[key]
            x = results.keys()
            y = [sample[mean] for sample in results.values()]
            yerr = [sample[std] for sample in results.values()]

            args = self._format_label_args(experiment,
                                           use_keys=isinstance(group, tuple))
            axes.errorbar(x, y, yerr=yerr, fmt='o-', label=", ".join(args))

        axes.legend(loc="best")
        group_key = self._get_group_name(group, separator="-")
        self._finish_plot("{}-{}".format(group_key, name.replace(" ", "-")))

    def _plot_knee(self, group, experiments, objective):
        multi_settings = isinstance(group, tuple) and len(group) > 1
        group_name = self._get_group_name(group)
        title = "Comparison of {} at knee points within {} group".format(objective, group_name)

        if multi_settings:
            xlabel = "settings"
        elif isinstance(group, tuple):
            xlabel = group[0]
        else:
            xlabel = group

        self._start_plot(title, xlabel, objective)

        axes = plt.gca()
        means = []
        stds = []
        labels = []
        for experiment in experiments.itervalues():
            means.append(experiment["knee"]["{}_knee".format(objective)])
            stds.append(experiment["knee"]["{}_std".format(objective)])

            args = self._format_label_args(experiment, use_keys=multi_settings)
            labels.append("\n".join(args))

        indices = np.arange(len(means))
        width = 0.5
        axes.bar(indices, means, width, yerr=stds, ecolor='r')
        axes.set_xticks(indices + width/2.0)
        axes.set_xticklabels(labels)

        group_key = self._get_group_name(group, separator="-")
        self._finish_plot("{}-comparison-{}".format(group_key, objective))

    def _finish_plot(self, name):
        filename = "{}/{}.pdf".format(self._results_path, name)
        plt.savefig(filename)
        print("Saved plot as {}".format(filename))

def main(argv):
    arguments = Arguments("settings.json", argv)
    results = Experiment_Results(arguments)

    arguments.check_help()

    try:
        results.execute()
    except:
        traceback.print_exc()
    finally:
        results.show_results()
        sys.exit(results.failed)

if __name__ == "__main__":
    main(sys.argv[1:])
