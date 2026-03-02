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
    print(f"out: {out}")
    matches = re.findall(rf'^\s*{re.escape(pkg)}/\d+(?:\.\d+)*\s*$', out, flags=re.MULTILINE)
    print(f"match: {matches}")
    #pat = re.compile(rf'^{re.escape(pkg)}/\d+(?:\.\d+)*\s*$', re.MULTILINE)
    #matches = pat.findall(out)

    #return matches if matches else []

def main():
    # Check conda version
    rVers = getCondaVersion()
    if rVers is None:
        print("Miniforge loaded. Run: module load miniforge")
        sys.exit(1)

    [main_package, version] = parse_arguments()

    # Check if the module is already installed
    #print(availableModules("hicexplorer"))
    availableModules("hicexplorer")
    #print(availableModules("baqlava"))

if __name__ == "__main__":
    main()