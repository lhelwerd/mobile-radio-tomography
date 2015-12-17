import re
import sys
import os
import shutil
import itertools
import subprocess
import numpy as np
from collections import OrderedDict

import matplotlib
# Make it possible to run matplotlib in SSH
NO_DISPLAY = 'DISPLAY' not in os.environ or os.environ['DISPLAY'] == ''
if NO_DISPLAY:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from settings import Arguments

def format_path(value):
    if isinstance(value, str):
        return value.replace('/', ',')
    else:
        return value

def format_arg(key, value):
    pair = []
    if key == "scenefile":
        scenes = {
            "castle": {
                "filename": "tests/vrml/castle.wrl",
                "translation": [0, -40, 0],
                "altitude": 4
            },
            "trees_river": {
                "filename": "tests/vrml/trees_river.wrl",
                "translation": [0, 0, 2.5],
                "altitude": 2.5
            },
            "deranged_house": {
                "filename": "tests/vrml/deranged_house.wrl",
                "translation": [4.1, 6.25, 0],
                "altitude": 0.5
            }
        }
        if value not in scenes:
            raise ValueError("Incorrect scene")

        pair += ["--translation"] + [str(t) for t in scenes[value]["translation"]]
        pair += ["--altitude", str(scenes[value]["altitude"])]
        value = scenes[value]["filename"]

    pair += ["--{}".format(key.replace('_','-')), str(value)]
    return pair

def generate(args, path):
    arg_pairs = [format_arg(k,v) for (k,v) in args.iteritems()]
    command = ["python", "{}/mission_basic.py".format(os.getcwd())]
    command += list(itertools.chain(*arg_pairs))
    command += ["--no-interactive", "--location-check"]

    with open("output.log","w") as output:
        with open("error.log","w") as error:
            retval = subprocess.call(command, stdout=output, stderr=error)
            print("Return value: {}".format(retval))

    if not os.path.exists(path):
        os.mkdir(path)

    files = ["output.log", "error.log", "plot.eps", "map.npy"]
    for file in files:
        if os.path.exists(file):
            shutil.move(file, path + "/" + file)

def process(args, path):
    errors = []
    count = 0
    max_time = False
    if os.path.exists(path + "/error.log") and os.path.getsize(path + "/error.log") > 0:
        errors.append("fatal-exception")
    with open(path + "/output.log") as f:
        log = f.read()
        if "Mission failed" in log:
            errors.append("runtime-error")
        if "Internal error" in log:
            errors.append("internal-error")
        if "Mission exceeded maximum execution time" in log:
            max_time = True

    if os.path.exists(path + "/map.npy"):
        map = np.load(path + "/map.npy")
        count = np.count_nonzero(map)

    return {
        "args": args,
        "errors": errors,
        "count": count,
        "max_time": max_time
    }

def main(argv):
    arguments = Arguments("settings.json", argv)
    settings = arguments.get_settings("simulations")
    arguments.check_help()

    # Search string to decide which experiments to do based on the combination 
    # name (so Mission_Square or padding-0.1 works) or based on error or output 
    # log contents
    filter = settings.get("filter")
    reverse = settings.get("reverse")
    process_path = settings.get("process_path")
    only_process = settings.get("only_process")

    permutations = OrderedDict([
        ("padding", [0.1, 4.0]),
        ("resolution", [1, 10]),
        ("space_size", [10, 100]),
        ("mission_class", ["Mission_Square", "Mission_Browse", "Mission_Search", "Mission_Pathfind"]),
        ("scenefile", ["castle", "trees_river", "deranged_house"]),
        ("closeness", [0.1, 2.0])
    ])
    new_args = {"space_size": 100}
    plot_groups = ["mission_class", "scenefile"]
    combinations = list(itertools.product(*permutations.values()))
    data = OrderedDict()
    i = -1
    for combination in combinations:
        i = i + 1
        print("{}/{} ({:4.0%})".format(i, len(combinations), i/float(len(combinations))))

        args = OrderedDict(zip(permutations.keys(), combination))
        path_args = [(k, format_path(v)) for (k,v) in args.iteritems()]
        path = '+'.join(["{}-{}".format(k,v) for (k,v) in path_args])
        old_path = '+'.join(["{}-{}".format(k,v) for (k,v) in path_args if k not in new_args or v != new_args[k]])
        full_path = process_path + "/" + path
        if old_path != path and os.path.exists(process_path + "/" + old_path):
            print("Moving to new path...")
            shutil.move(process_path + "/" + old_path, full_path)

        print(path)
        stop = False
        if filter != "" and re.search(filter, path) is None:
            if os.path.exists(full_path):
                search_files = ["output.log", "error.log"]
                for file in search_files:
                    with open(full_path + "/" + file) as f:
                        if re.search(filter, f.read()) is not None:
                            print("Found filter in {}".format(file))
                            if reverse:
                                stop = True
                            else:
                                break
                else:
                    if not reverse:
                        print("Skipped: Not in output logs")
                        continue
            elif not reverse:
                print("Skipped: Not in arguments")
                continue
        elif reverse:
            print("Skipped: Filter found in path")

        if stop:
            continue

        if process_path != "" and os.path.exists(full_path):
            data[path] = process(args, full_path)
        elif not only_process:
            generate(args, full_path)

    if data:
        bar_width = 0.5

        # Plot of feasible runs
        counts = []
        labels = []
        for combination, info in data.iteritems():
            if not info["errors"] and info["count"] >= 20:
                counts.append(info["count"])
                arg_label = [v.split('_')[-1] for (k,v) in info["args"].iteritems() if k in plot_groups]
                labels.append('\n'.join(arg_label))

        x_groups = np.arange(len(counts))

        fig, ax = plt.subplots()
        colors = [(x/float(len(counts)), x/float(2*len(counts)), 0.75) for x in range(len(counts))]
        rects = ax.bar(x_groups, counts, bar_width, color=colors, ecolor='k')

        ax.set_xlabel('Parameters')
        ax.set_ylabel('Memory map count')
        ax.set_title('Feasible')
        plt.xticks(x_groups + (bar_width / 2.0), ha='center')
        ax.set_xticklabels(labels)

        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # Grouped plots
        group_combinations = itertools.product(*[permutations[g] for g in plot_groups])
        for group in group_combinations:
            counts = []
            labels = []
            colors = []
            for combination, info in data.iteritems():
                group_value = tuple(info["args"][g] for g in plot_groups)
                if group_value == group:
                    counts.append(info["count"])
                    arg_label = ["{}={}".format(k,v) for (k,v) in info["args"].iteritems() if k not in plot_groups]
                    print(arg_label)
                    labels.append('\n'.join(arg_label))
                    if info["errors"]:
                        print(info["errors"])
                        colors.append('r')
                    elif info["max_time"]:
                        colors.append('b')
                    else:
                        colors.append('g')

            x_groups = np.arange(len(counts))
            fig, ax = plt.subplots()
            rects = ax.bar(x_groups, counts, bar_width, color=colors, ecolor='k')

            ax.set_xlabel('Parameters')
            ax.set_ylabel('Memory map count')
            ax.set_title(', '.join(group))
            plt.xticks(x_groups + (bar_width / 2.0), ha='center')
            ax.set_xticklabels(labels)

            plt.grid(True)
            plt.tight_layout()
            plt.show()

if __name__ == "__main__":
    main(sys.argv[1:])
