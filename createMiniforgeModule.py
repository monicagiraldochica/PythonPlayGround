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

    input("sudo su - [Enter]")
    input("ml load miniforge [Enter]")

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
            msg = f"\nA previous miniforge environment was created for {main_package} ({', '.join(downloads)}), "

            # The miniforge environment was previously created, but not the module
            if (not os.path.isdir(ml_folder)):
                create_env = False
                msg+="but not the module.\nDo you want to proceed? [y/N]: "

            # The module was created at some point, but it was disabled
            else:
                msg+=f"and there's a module folder for this app ({ml_folder}). However, the module is not available.\nDo you want to proceed? [y/N]: "            

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

        elif os.path.isdir(apps_path):
            msg = f"{main_package} was previously downloaded in /hpc/apps/{main_package}, outside miniforge, but no module was created.\nContent of {apps_path}:\n{contentFolder(apps_path)}\nDo you want to proceed? [y/N]: "

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

    use_pip = input("\nAre you installing using pip inside this conda environment? [Y/n]: ").strip().lower() not in ("n", "not")
    env_name = f"{main_package}-{version}"
    if create_env:
        venv_python = input(f"What python version is required by {main_package}/{version} (i.e. python>=3.10, Enter if no specific version required): ")
        if (not venv_python) and use_pip:
            print("*** YOU NEED TO INSTALL PYTHON INSIDE THE CONDA ENV OR IT WILL INSTALL THE PROGRAM IN BASE ***")
            venv_python = f"python={major}.{minor}.{micro}"
        
        if (not venv_python):
            input(f"\nconda create -n {env_name} [Enter]")
        else:
            input(f"\nconda create -n {env_name} {venv_python} [Enter]")

    input(f"\nconda activate {env_name} [Enter]")

    if input("\nDo you need to clone any repos? [y/N]: ").strip().lower() in ("y", "yes"):
        repos = input("https git repos divided by comma: ").split(",")
        if len(repos)>0:
            build_path = f"/adminfs/builds/{main_package}"
            if not os.path.isdir(build_path):
                os.mkdir(build_path)
            build_path = f"{build_path}/downloads"
            if not os.path.isdir(build_path):
                os.mkdir(build_path)

            for repo in repos:
                repo_name = repo.split("/")[-1].replace(".git", "")
                dest = f"{build_path}/{repo_name}"

                if not os.path.isdir(dest):
                    input(f"\nDownloading {repo} to {dest} [Enter]")
                    cmd = ["git", "clone", repo, dest]
                    print(" ".join(cmd))
                    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

                    if result.returncode!=0 or (not os.path.isdir(dest)):
                        err = result.stderr or result.stdout
                        print(f"Could not download {repo_name}: {err}")
                        sys.exit(1)

                    input(f"Successfully downloaded {repo_name} [Enter]")

                else:
                    print(f"\n{dest} already exists")

    if use_pip:
        which_pip = input(f"\nrun 'which pip' and paste here the output: ")
        if which_pip!=f"/hpc/apps/miniforge/envs/{env_name}/bin/pip":
            input("*** DO NOT PROCEED UNTIL YOU THE RESULT OF which pip IS /hpc/apps/miniforge/envs/{env_name}/bin/pip *** [Enter]")

        print("\nAfter each pip install run 'conda list | grep <program>' to check that it was indeed installed, and run any tests.\nDo not proceed with the next dependency until the previous one is installed and tested.\nRemember to add the version of each dependency if a specific version is needed!\n")
        pips = input("List of programs to install using pip divided by comma: ").split(",")
        for pip_install in pips:
            input(f"pip install {pip_install} [Enter]")
            input(f"conda list | grep {pip_install} [Enter]")
            input("Run a test command [Enter]")
                
if __name__ == "__main__":
    main()