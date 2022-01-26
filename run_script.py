#!/usr/bin/env python

import sys
import os

scripts = [path.rstrip(".py") for path in os.listdir("./scripts")
           if path.endswith(".py") and not path.startswith("__")]
scripts.sort()

def print_scripts():
    print("These are your available scripts:")
    for path in scripts:
        print(f"\t{path}")


if len(sys.argv) == 1:
    print_scripts()
    exit()

script = sys.argv[1]

if script not in scripts:
    print(f"'{script}'is not an available option")
    print()
    print_scripts()
    exit()

__import__(f"scripts.{script}")