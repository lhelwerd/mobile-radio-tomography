import re
import sys
import os
import shutil
import itertools
import subprocess
import datetime
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
    run_time = 0.0
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
        m = re.search("run time: ([\d.]+) s", log)
        if m is not None:
            run_time = float(m.group(1))

    if os.path.exists(path + "/map.npy"):
        map = np.load(path + "/map.npy")
        count = np.count_nonzero(map)

    return {
        "args": args,
        "path": path,
        "errors": errors,
        "count": count,
        "max_time": max_time,
        "run_time": run_time
    }

def format_plot_arg(key, value):
    return "{}={}".format(key.split('_')[0], str(value).split('_')[-1])

def process_plot_data(data, group=(), plot_groups=(), include=None):
    counts = []
    labels = []
    colors = []
    times = []

    for combination, info in data.iteritems():
        group_value = tuple(info["args"][g] for g in plot_groups)
        if group_value == group and (include is None or include(info)):
            counts.append(info["count"])
            arg_label = [format_plot_arg(k,v) for (k,v) in info["args"].iteritems() if k not in plot_groups]
            labels.append('\n'.join(arg_label))
            times.append("{:0>8}".format(datetime.timedelta(seconds=int(info["run_time"]))))
            if info["errors"]:
                colors.append('r')
            elif info["max_time"]:
                colors.append('b')
            else:
                colors.append('g')

    return {
        "counts": counts,
        "labels": labels,
        "colors": colors,
        "times": times
    }

def make_plot(plot_data, title="Memory map per run", output_dir="", filename=None):
    bar_width = 0.5
    x_groups = np.arange(len(plot_data["counts"]))

    fig, ax = plt.subplots()
    rects = ax.bar(x_groups, plot_data["counts"], bar_width, color=plot_data["colors"], ecolor='k')

    ax.set_xlabel('Parameters')
    ax.set_ylabel('Memory map count')
    ax.set_title(title)
    plt.xticks(x_groups + (bar_width / 2.0), ha='center')
    ax.set_xticklabels(plot_data["labels"])

    for (rect, label) in zip(rects, plot_data["times"]):
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width()/2., 1.05*height, label, ha='center', va='bottom')

    plt.grid(True)
    plt.tight_layout()
    if NO_DISPLAY:
        if filename is None:
            filename = title

        plt.savefig(output_dir + filename + '.pdf')
    else:
        plt.show()

def make_table(bests, permutations, plot_groups, key, output_dir=""):
    last_group = plot_groups[-1]
    cols = len(permutations[last_group])
    group_combinations = itertools.product(*[permutations[g] for g in plot_groups])
    with open(output_dir + key + '.tex', 'w') as f:
        f.write("\\begin{table}[hb]\n  \\centering\n  \\begin{tabular}{|c|")
        f.write("c|" * cols)
        f.write("}\n    ")

        for p in permutations[last_group]:
            f.write(" & \\verb+{}+".format(p))

        cur_group = None
        for group in group_combinations:
            if cur_group != group[0]:
                cur_group = group[0]
                f.write(" \\\\ \hline\n    \\verb+{}+".format(cur_group))
            f.write(" & {}".format(bests[group][key]))

        f.write(" \\\\ \hline\n  \end{tabular}\n  \caption{")
        f.write("Best {0}s for each {1}".format(key, " and ".join(plot_groups).replace('_',' ')))
        f.write("}\label{tab:" + key + "}\n\end{table}")

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
    output_path = settings.get("output_path")
    only_process = settings.get("only_process")

    permutations = OrderedDict([
        ("padding", [0.1, 2.0, 4.0]),
        ("resolution", [1, 10]),
        ("space_size", [10, 100]),
        ("mission_class", ["Mission_Square", "Mission_Browse", "Mission_Search", "Mission_Pathfind"]),
        ("scenefile", ["castle", "trees_river", "deranged_house"]),
        ("closeness", [0.1, 2.0]),
        ("step_delay", [0.25, 0.5])
    ])
    new_args = {"space_size": 100, "step_delay": 0.5}
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
        full_path = process_path + "/" + path
        for new_arg, default_val in new_args.iteritems():
            old_path = '+'.join(["{}-{}".format(k,v) for (k,v) in path_args if k != new_arg or v != default_val])
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

        if not only_process and not os.path.exists(full_path):
            generate(args, full_path)
        if process_path != "" and os.path.exists(full_path):
            data[path] = process(args, full_path)

    if data:
        # Plot of feasible runs
        plot_data = process_plot_data(data, include=lambda info: not info["errors"] and info["count"] > 50)

        length = len(plot_data["counts"])
        plot_data["colors"] = [(x/float(length), x/float(2*length), 0.75) for x in range(length)]

        make_plot(plot_data, title="Feasible")

        # Grouped plots
        group_combinations = itertools.product(*[permutations[g] for g in plot_groups])
        bests = {}
        for group in group_combinations:
            plot_data = process_plot_data(data, group, plot_groups)

            make_plot(plot_data, title=', '.join(group), output_dir=output_path, filename='-'.join(group))

            best_idx = np.argmax(plot_data["counts"])
            bests[group] = {
                "label": plot_data["labels"][best_idx],
                "count": plot_data["counts"][best_idx],
                "time": plot_data["times"][best_idx]
            }

        make_table(bests, permutations, plot_groups, "count", output_path)
        make_table(bests, permutations, plot_groups, "time", output_path)

if __name__ == "__main__":
    main(sys.argv[1:])
