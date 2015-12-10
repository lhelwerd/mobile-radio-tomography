import sys
import os
import shutil
import itertools
import subprocess
from collections import OrderedDict

def format_arg(key, value):
    pair = []
    if key == "scenefile":
        scenes = {
            "castle": {
                "filename": "tests/vrml/castle.wrl",
                "translation": [0, -40, 0]
            },
            "trees_river": {
                "filename": "tests/vrml/trees_river.wrl",
                "translation": [0, 0, 2.5]
            },
            "deranged_house": {
                "filename": "tests/vrml/deranged_house.wrl",
                "translation": [4.1, 6.25, 0]
            }
        }
        if value not in scenes:
            raise ValueError("Incorrect scene")

        pair += ["--translation"] + [str(t) for t in scenes[value]["translation"]]
        value = scenes[value]["filename"]

    pair += ["--{}".format(key.replace('_','-')), str(value)]
    return pair

def main(argv):
    permutations = OrderedDict([
        ("mission_class", ["Mission_Square", "Mission_Browse", "Mission_Search", "Mission_Pathfind"]),
        ("scenefile", ["castle", "trees_river", "deranged_house"]),
        ("closeness", [0.1, 2.0]),
        ("padding", [0.1, 4.0]),
        ("resolution", [1, 5])
    ])
    for combination in itertools.product(*permutations.values()):
        arguments = dict(zip(permutations.keys(), combination))
        path = '+'.join(["{}-{}".format(k,v.replace('/',',') if isinstance(v,str) else v) for (k,v) in arguments.iteritems()])
        print(path)

        arg_pairs = [format_arg(k,v) for (k,v) in arguments.iteritems()]
        args = list(itertools.chain(*arg_pairs))

        with open("output.log","w") as output:
            with open("error.log","w") as error:
                retval = subprocess.call(["python", "{}/mission_basic.py".format(os.getcwd())] + args + ["--no-interactive", "--location-check"], stdout=output, stderr=error)
                print("Return value: {}".format(retval))

        if not os.path.exists(path):
            os.mkdir(path)

        files = ["output.log", "error.log", "plot.eps", "map.npy"]
        for file in files:
            if os.path.exists(file):
                shutil.move(file, path + "/" + file)

if __name__ == "__main__":
    main(sys.argv[1:])
