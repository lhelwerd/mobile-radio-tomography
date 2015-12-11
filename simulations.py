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

def generate(arg_combinations, path):
    arg_pairs = [format_arg(k,v) for (k,v) in arg_combinations.iteritems()]
    args = ["python", "{}/mission_basic.py".format(os.getcwd())]
    args += list(itertools.chain(*arg_pairs))
    args += ["--no-interactive", "--location-check"]

    with open("output.log","w") as output:
        with open("error.log","w") as error:
            retval = subprocess.call(args, stdout=output, stderr=error)
            print("Return value: {}".format(retval))

    if not os.path.exists(path):
        os.mkdir(path)

    files = ["output.log", "error.log", "plot.eps", "map.npy"]
    for file in files:
        if os.path.exists(file):
            shutil.move(file, path + "/" + file)

def process(arg_combination, path):
    return {
        "combination": arg_combination,
        "errors": [],
        "count": 0
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
        ("mission_class", ["Mission_Square", "Mission_Browse", "Mission_Search", "Mission_Pathfind"]),
        ("scenefile", ["castle", "trees_river", "deranged_house"]),
        ("closeness", [0.1, 2.0]),
        ("padding", [0.1, 4.0]),
        ("resolution", [1, 5])
    ])
    combinations = list(itertools.product(*permutations.values()))
    data = {}
    i = -1
    for combination in combinations:
        i = i + 1
        print("{}/{} ({:4.0%})".format(i, len(combinations), i/float(len(combinations))))

        arg_combinations = dict(zip(permutations.keys(), combination))
        path = '+'.join(["{}-{}".format(k, format_path(v)) for (k,v) in arg_combinations.iteritems()])
        full_path = process_path + "/" + path
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

        if process_path != "" and os.path.exists(process_path):
            data[path] = process(arg_combinations, full_path)
        else:
            generate(arg_combinations, full_path)

    print(data)

if __name__ == "__main__":
    main(sys.argv[1:])
