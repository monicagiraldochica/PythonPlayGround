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
    out = contentFolder(path)
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

    [main_package, version] = parse_arguments()

    # The module is already installed
    ml_avail = availableModules(main_package)
    create_env = True

    if f"{main_package}/{version}" in ml_avail:
        print(f"Good news! {main_package}/{version} is already installed!")
        sys.exit(1)
    
    # A different version of the module was installed
    elif len(ml_avail)>0:
        if input(f"A different version of {main_package} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {main_package}/{version}? [y/N]: ").strip().lower() not in ("yes", "y"):
            sys.exit(1)
    
    else:
        downloads = downloadedMiniforgeVersions(main_package, "/hpc/apps/miniforge/envs")
        apps_path = f"/hpc/apps/{main_package}"

        if len(downloads)>0:
            ml_folder = f"/hpc/modulefiles/{main_package}"
            msg = f"A previous miniforge environment was created for {main_package} ({', '.join(downloads)}), "

            # The miniforge environment was previously created, but the module not
            if os.path.isdir(ml_folder):
                create_env = False
                msg+="but not the module.\nDo you want to proceed? [y/N]: "

            # The module was created at some point, but it was disabled
            else:
                msg+=f"and there's a module folder for this app ({ml_folder}) in /hpc/modulefiles/{main_package}. However, the module is not available.\nDo you want to proceed? [y/N]: "            

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

        elif os.path.isdir(apps_path):
            msg = f"{main_package} was previously downloaded in /hpc/apps/{main_package}, outside miniforge, but no module was created.\nContent of {apps_path}:\n{contentFolder(apps_path)}\nDo you want to proceed? [y/N]: "

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

    if create_env:
        env_name = f"{main_package}-{version}"
        print(f"conda create -n {env_name}")
        subprocess.run(["conda", "create", "-y", "-n", env_name, f"{main_package}={version}"], check=True)
                
if __name__ == "__main__":
    main()