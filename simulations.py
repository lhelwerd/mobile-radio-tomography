import sys
import os
import shutil
import itertools
import subprocess
from collections import OrderedDict

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

    return {
        "args": args,
        "errors": errors,
        "count": count,
        "max_time": max_time
    }

def main(argv):
    arguments = Arguments("settings.json", argv)
    settings = arguments.get_settings("simulations")

    # Search string to decide which experiments to do based on the combination 
    # name (so Mission_Square or padding-0.1 works) or based on error or output 
    # log contents
    filter = settings.get("filter")
    process_path = settings.get("process_path")

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
        if os.path.exists(process_path + "/" + old_path):
            print("Moving to new path...")
            shutil.move(process_path + "/" + old_path, full_path)

        print(path)
        if filter != "" and filter not in path:
            if os.path.exists(full_path):
                search_files = ["output.log", "error.log"]
                for file in search_files:
                    with open(full_path + "/" + file) as f:
                        if filter in f.read():
                            print("Found filter in {}".format(file))
                            break
                else:
                    print("Skipped: Not in output logs")
                    continue
            else:
                print("Skipped: not in arguments")
                continue

        if process_path != "" and os.path.exists(full_path):
            data[path] = process(args, full_path)
        else:
            generate(args, full_path)

if __name__ == "__main__":
    main(sys.argv[1:])
