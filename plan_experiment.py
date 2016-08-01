import itertools
import json
import os
import sys
import traceback
from subprocess import Popen
from __init__ import __package__
from settings import Arguments

class Experiment_Runner(object):
    def __init__(self, arguments):
        self._arguments = arguments
        self._settings = self._arguments.get_settings("planning_experiments")
        self._number_of_processes = self._settings.get("number_of_processes")
        self._pass_environment = self._settings.get("pass_environment")

        planning_components = (
            "planning", "planning_runner",
            "planning_algorithm", "planning_problem",
            "planning_assignment", "planning_collision_avoidance"
        )
        self._settings_infos = {}
        self._settings_overrides = []
        for component in planning_components:
            settings = self._arguments.get_settings(component)
            self._settings_infos.update(settings.get_info())

            for setting, value in settings.get_all():
                if not settings.is_default(setting):
                    args = self._format_arg(setting, value)
                    self._settings_overrides.extend(args)

        # On Unix platforms, the `close_fds` argument closes all other file 
        # descriptors than the standard ones (0, 1, and 2). This is because the 
        # file descriptors are inherited from the parent process, so we close 
        # them in the subprocesses for sanity and reduced risk of any 
        # interference. However, on Windows, `close_fds` closes all inherited 
        # handles, including the standard ones, and causes them to be unable to 
        # be redirected for the specific subprocesses.
        self._use_closed_pipes = "posix" in sys.builtin_module_names

        if self._pass_environment:
            self._environment = os.environ
        else:
            self._environment = {}

        # Python flags that are passed through to the runners.
        flags = {
            "O": sys.flags.optimize,
            "B": sys.flags.dont_write_bytecode,
            "s": sys.flags.no_user_site,
            "S": sys.flags.no_site,
            "E": sys.flags.ignore_environment,
            "t": sys.flags.tabcheck,
            "v": sys.flags.verbose
        }

        self._program = [sys.executable]
        if self._pass_environment:
            for flag, value in flags.iteritems():
                if value > 0:
                    self._program.append("-{}".format(flag * value))

        self._program.append("plan_reconstruct.py")
        self._program.extend(self._settings_overrides)

        with open("planning/experiments.json", "r") as experiments_file:
            self._experiments = json.load(experiments_file)

        self._total = 0
        self._failed = 0
        
    def execute(self):
        self._total = 0
        self._failed = 0

        for experiment in self._experiments:
            setting_keys = experiment.keys()
            try:
                setting_values = [
                    self._get_setting_options(setting, options)
                    for setting, options in experiment.iteritems()
                ]
            except ValueError:
                traceback.print_exc()
                self._fail(1)

            combinations = itertools.product(*setting_values)
            for combination in combinations:
                self._run(setting_keys, combination)

    def show_results(self):
        print("------------------------------")
        print("Number of experiments run: {}".format(self._total))
        print("Number of failures: {}".format(self._failed))

    @property
    def failed(self):
        return self._failed

    def _fail(self, count):
        self._failed += count
        print("{} {} failed".format(count, "experiment" if count == 1 else "experiments"))

    def _get_setting_options(self, setting, options):
        if options is None:
            if setting not in self._settings_infos:
                raise ValueError("Setting '{}' is not registered".format(setting))

            info = self._settings_infos[setting]
            if info["type"] == "bool":
                return (True, False)

            options = self._arguments.get_choices(info)
            if options is None:
                raise ValueError("Setting '{}' has no options in experiments or info".format(setting))

        return options

    def _run(self, setting_keys, setting_values):
        self._total += self._number_of_processes

        # The arguments for this experiment
        formatted_args = self._format_args(setting_keys, setting_values)
        # The arguments as well as the ones provided to the experiment runner
        settings_args = self._settings_overrides + formatted_args

        print("Full arguments list: {}".format(" ".join(settings_args)))

        # The subprocess call, with Python flags and the full list of arguments
        args = self._program + formatted_args

        processes = []
        output_logs = []
        error_logs = []
        for i in range(self._number_of_processes):
            path = "results/{}-{}".format("-".join(settings_args), i)
            if not os.path.exists(path):
                os.mkdir(path)

            # Open some writable files to redirect the standard output and 
            # standard error pipes to. This is useful for later log analysis, 
            # and keeps the main process output clean. We enable line buffering 
            # with `bufsize` so that we can see almost-live progress by reading 
            # the files.
            output_file = open("{}/output.log".format(path), "w+")
            error_file = open("{}/error.log".format(path), "w+")

            environment = self._environment.copy()
            environment.update({
                "DISPLAY": "",
                "SAVE_PATH": path
            })

            # Start the subprocess and register all its information.
            process = Popen(args, stdout=output_file, stderr=error_file,
                            bufsize=1, close_fds=self._use_closed_pipes,
                            env=environment)

            processes.append(process)
            output_logs.append(output_file)
            error_logs.append(error_file)

        print("Started {} processes".format(self._number_of_processes))

        exit_count = self._wait(processes)
        self._close_files(output_logs)
        error_count = self._close_files(error_logs)

        if exit_count > 0 or error_count > 0:
            self._fail(max(exit_count, error_count))

    def _format_args(self, setting_keys, setting_values):
        args = []
        for setting, option in zip(setting_keys, setting_values):
            args.extend(self._format_arg(setting, option))

        return args

    def _format_arg(self, setting, option):
        setting_arg = setting
        if option is False:
            setting_arg = "no_{}".format(setting_arg)

        setting_arg = "--{}".format(setting_arg.replace('_', '-'))

        args = [setting_arg]
        if isinstance(option, (tuple, list)):
            args.extend([str(value) for value in option])
        elif not isinstance(option, bool):
            args.append(str(option))

        return args

    def _wait(self, processes):
        # Wait until all processes have finished.
        count = 0
        for process in processes:
            process.wait()
            if process.returncode != 0:
                print("Process returned with exit code {}".format(process.returncode))
                count += 1

        return count

    def _close_files(self, files):
        count = 0
        for output_file in files:
            if output_file.tell() > 0:
                count += 1

            print("{}: {} bytes".format(output_file.name, output_file.tell()))
            output_file.close()

        return count

def main(argv):
    arguments = Arguments("settings.json", argv)
    runner = Experiment_Runner(arguments)

    arguments.check_help()

    try:
        runner.execute()
    except:
        traceback.print_exc()
    finally:
        runner.show_results()
        sys.exit(runner.failed)

if __name__ == "__main__":
    main(sys.argv[1:])
