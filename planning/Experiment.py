import itertools
import json
from planning import COMPONENTS

class Experiment(object):
    def __init__(self, arguments):
        self._arguments = arguments
        self._settings_infos = {}
        self._settings_overrides = []

        for component in COMPONENTS:
            settings = self._arguments.get_settings(component)
            self._settings_infos.update(settings.get_info())

            for setting, value in settings.get_all():
                if not settings.is_default(setting):
                    args = self.format_arg(setting, value)
                    self._settings_overrides.extend(args)

        with open("planning/experiments.json", "r") as experiments_file:
            self._experiments = json.load(experiments_file)

    def get_options(self, experiment):
        setting_keys = experiment.keys()
        setting_values = [
            self._get_setting_options(setting, options)
            for setting, options in experiment.iteritems()
        ]

        combinations = itertools.product(*setting_values)
        return setting_keys, combinations

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

    def format_args(self, setting_keys, setting_values):
        args = []
        for setting, option in zip(setting_keys, setting_values):
            args.extend(self.format_arg(setting, option))

        return args

    def format_arg(self, setting, option):
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
