# Core imports
import glob
import os
import re
import sys
import traceback
from collections import OrderedDict

# Library imports
import numpy as np

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
        self._results_path = self._settings.get("results_path")

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
            }
        }

        for pattern in self._log_patterns.itervalues():
            pattern["regex"] = re.compile(pattern["regex"])

        self._errors = 0
        self._total = 0

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

    def show_results(self):
        dir_count = len(glob.glob("{}/*/".format(self._results_path)))
        print("------------------------------")
        print("Number of experiments: {}".format(self._total))
        print("Number of directories containing results: {}".format(dir_count))
        print("Number of problems: {}".format(self._errors))

    def _run(self, setting_keys, combination):
        formatted_args = self.format_args(setting_keys, combination)
        settings_args = self._settings_overrides + formatted_args
        args = "-".join(settings_args)

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
            self._output(total_results)

    def _parse_output_log(self, path, data):
        current = {
            "iteration": -1,
            "individual": -1
        }
        data["iteration"] = {}
        data["individual"] = {}
        with open("{}/output.log".format(path), "r") as output_log:
            for line in output_log:
                for pattern in self._log_patterns.itervalues():
                    matches = pattern["regex"].match(line)
                    if matches:
                        values = self._cast(pattern["casts"], matches.groups())
                        groups = dict(zip(pattern["names"], values))
                        data_group = pattern["group"]
                        if data_group in groups:
                            current[data_group] = groups[data_group]
                            del groups[data_group]

                        identifier = current[data_group]
                        if identifier not in data[data_group]:
                            data[data_group][identifier] = {}

                        data[data_group][identifier].update(groups)

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

        iteration_limit = max(its.keys())
        if len(ins) > 0:
            knee = np.array([
                its[iteration_limit][obj] for obj in self._objectives
            ])
        else:
            knee = np.array([np.inf] * len(self._objectives))

        data["results"] = {
            "knee": knee
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

        for algorithm in self._algorithms:
            key = "contribution_{}".format(algorithm.get_name())
            if len(individuals) == 0:
                contribution = np.inf
            else:
                contribution = algorithm.sort_contribution(individuals)

            data["results"][key] = np.median(contribution)

    def _sample(self, process_results):
        # sample results from multiple processes (mean/median, std dev, var)
        if len(process_results) == 0:
            return {}

        total_results = {}
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
        sample_funcs = ["mean", "std", "median", "min", "max", "var"]
        results = np.array(results)
        if np.any(results == np.inf):
            return dict([(key, np.inf) for key in sample_funcs])

        return dict([
            (key, getattr(np, key)(results, axis=0)) for key in sample_funcs
        ])

    def _output(self, experiment_results):
        pass

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
