import sys
import os
import shutil
import itertools
import subprocess
from collections import OrderedDict

def main(argv):
    permutations = OrderedDict([
        ("mission_class", ["Mission_Square", "Mission_Browse", "Mission_Search", "Mission_Pathfind"]),
        ("scenefile", ["tests/vrml/castle.wrl", "tests/vrml/trees_river.wrl", "tests/vrml/deranged_house.wrl"]),
        ("closeness", [0.1, 2.0]),
        ("padding", [0.1, 4.0]),
        ("resolution", [1, 5])
    ])
    for combination in itertools.product(*permutations.values()):
        arguments = dict(zip(permutations.keys(), combination))
        path = '+'.join(["{}-{}".format(k,v.replace('/',',') if isinstance(v,str) else v) for (k,v) in arguments.iteritems()])
        print(path)

        args = list(itertools.chain(*[["--{}".format(k.replace('_','-')), str(v)] for (k,v) in arguments.iteritems()]))

        with open("output.log","w") as output:
            with open("error.log","w") as error:
                retval = subprocess.call(["python", "{}/mission_basic.py".format(os.getcwd())] + args + ["--no-interactive", "--location-check"], stdout=output, stderr=error)
                print("Return value: {}".format(retval))

        if not os.path.exists(path):
            os.mkdir(path)

        files = ["output.log", "error.log", "plot.eps", "map.npy"]
        for file in files:
            if os.path.exists(path):
                shutil.move(file, path + "/" + file)

if __name__ == "__main__":
    main(sys.argv[1:])
