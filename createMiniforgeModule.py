#!/usr/bin/env python3
__author__ = "Monica Keith"

import subprocess
import sys
import argparse
import re

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install bew nodule using miniforge")
    parser.add_argument("--main-package", help="Name of the module to be created", required=True)
    parser.add_argument("--version", help="Module version", required=True)
    args = parser.parse_args()

    return [args.main_package, args.version]

def getCondaVersion():
    try:
        result = subprocess.run(["conda","--version"], check=True, capture_output=True, text=True).stdout
        match = re.search(r"(\d+\.\d+\.\d+)", result)
        return match.group(1) if match else None
    
    except FileNotFoundError:
        return None
    
    except subprocess.CalledProcessError:
        return None

def availableModules(pkg):
    cmd = f"module avail {pkg}"
    result = subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")
    matches = re.findall(rf'\b{re.escape(pkg)}/[^\s]+', out)

    return matches

def main():
    # Check conda version
    rVers = getCondaVersion()
    if rVers is None:
        print("Miniforge loaded. Run: module load miniforge")
        sys.exit(1)

    [main_package, version] = parse_arguments()

    # Check if the module is already installed
    print(availableModules("python"))
    print(availableModules("hicexplorer"))
    print(availableModules("baqlava"))

if __name__ == "__main__":
    main()