#!/usr/bin/env python3
__author__ = "Monica Keith"

import subprocess
import sys
import argparse
import re
import os

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

def contentFolder(path):
    path = path[:-1] if path.endswith("/") else path
    cmd = f"ls -1 {path}"
    result = subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")

    return out

def downloadedMiniforgeVersions(pkg, path):
    path = path[:-1] if path.endswith("/") else path
    cmd = f"ls -1 {path}"
    result = subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")
    names = re.findall(rf'^{re.escape(pkg)}-[^/\s]+$', out, flags=re.MULTILINE)

    return [f"{path}/{name}" for name in names]

def main():
    # Check conda version
    rVers = getCondaVersion()
    if rVers is None:
        print("Miniforge loaded. Run: module load miniforge")
        sys.exit(1)

    # Check python version
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    print(f"Python version: {major}.{minor}.{micro}\n")
    if major==0 or minor==0 or major<3 or minor<7:
        print("This script requires Python 3.7 or higher.")
        sys.exit(1)

    print(contentFolder("/hpc/apps/miniforge/envs/hicexplorer-3.7.6"))

    #[main_package, version] = parse_arguments()

    # Check if the module is already installed
    #ml_avail = availableModules(main_package)
    #if f"{main_package}/{version}" in ml_avail:
    #    print(f"Good news! {main_package}/{version} is already installed!")
    #    sys.exit(1)
    #elif len(ml_avail)>0:
    #    if input(f"A different version of {main_package} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {main_package}/{version}? [y/N]: ").strip().lower() not in ("yes", "y"):
    #        sys.exit(1)
    #else:
    #    downloads = downloadedMiniforgeVersions(main_package, "/hpc/apps/miniforge/envs")
    #    if len(downloads)>0:
    #        ml_folder = f"/hpc/modulefiles/{main_package}"
    #        msg = f"A previous miniforge environment was created for {main_package} ({', '.join(downloads)}), "
    #        if os.path.isdir(ml_folder):
    #            msg+="but not the module.\nDo you want to proceed? [y/N]: "
    #        else:
    #            msg+=f"and there's a module folder for this app ({ml_folder}). However, the module is not available.\nDo you want to proceed? [y/N]: "

    #        if input(msg).strip().lower() not in ("yes", "y"):
    #            sys.exit()

    #    elif os.path.isdir(f"/hpc/apps/{main_package}"):
    #        msg = f"{main_package} was previously downloaded in /hpc/apps, outside miniforge, but no module was created.\nDo you want to proceed? [y/N]: "

    #        if input(msg).strip().lower() not in ("yes", "y"):
    #            sys.exit()

    #print(contentFolder("/hpc/apps/miniforge/envs/hicexplorer-3.7.6"))

if __name__ == "__main__":
    main()