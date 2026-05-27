#!/usr/bin/env python3
__author__ = "Monica Keith"

import sys
import argparse
import re
import os
import installib
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install bew nodule using miniforge")
    parser.add_argument("--main-pkg", help="Name of the module to be created", required=True)
    parser.add_argument("--version", help="Module version", required=True)
    args = parser.parse_args()

    return [args.main_pkg, args.version]

def getCondaVersion():
    returncode, stderr, stdout = installib.runBash(["conda", "--version"])

    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"ERROR: Could not check conda version: {err}")
        return None
    
    match = re.search(r"(\d+\.\d+\.\d+)", stdout)
    return match.group(1) if match else None

def downloadedMiniforgeVersions(pkg: str, path:str):
    out = installib.contentFolder(path)
    if out is None:
        return []
    
    names = re.findall(rf'^{re.escape(pkg)}-[^/\s]+$', out, flags=re.MULTILINE)
    return [f"{path}/{name}" for name in names]

def main():
    # Check python version
    correct_python, major, minor, micro = installib.checkPythonVers(3, 7)
    if not correct_python:
        print("ERROR: This script requires Python 3.7 or higher\n")
        sys.exit(1)

    # Make sure I'm root in a login node, and miniforge is loaded
    input("\nssh into login node [Enter]")
    input("sudo su - [Enter]")
    input("ml load miniforge [Enter]")

    [main_pkg, version] = parse_arguments()

    # Paths
    ml_folder = f"/hpc/modulefiles/{main_pkg}"
    new_ml = f"{ml_folder}/{version}.lua"
    forge_envs = "/hpc/apps/miniforge/envs"
    env_name = f"{main_pkg}-{version}"
    forge_dir = f"{forge_envs}/{env_name}"
    forge_path = f"{forge_dir}/bin"
    apps_path = f"/hpc/apps/{main_pkg}"
    db_folder = f"/hpc/refdata/{main_pkg}"

    ml_avail = installib.availableModules(main_pkg)
    create_env = True

    # The module is already installed
    if f"{main_pkg}/{version}" in ml_avail:
        print(f"\nGood news! {main_pkg}/{version} is already installed!")
        sys.exit(1)
    
    # A different version of the module was installed
    elif len(ml_avail)>0:
        if input(f"\nA different version of {main_pkg} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {main_pkg}/{version}? [y/N]: ").strip().lower() not in ("yes", "y"):
            sys.exit(1)
    
    else:
        downloads = downloadedMiniforgeVersions(main_pkg, forge_envs)

        if len(downloads)>0:
            msg = f"\nA previous miniforge environment was created for {main_pkg} ({', '.join(downloads)}), "

            # The miniforge environment was previously created, but not the module
            if (not os.path.isdir(ml_folder)):
                create_env = False
                msg+="but not the module.\nDo you want to proceed? [y/N]: "

            # The module was created at some point, but it was disabled
            else:
                msg+=f"and there's a module folder for this app ({ml_folder}). However, the module is not available.\nDo you want to proceed? [y/N]: "           

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit(1)

        elif os.path.isdir(apps_path):
            msg = f"{main_pkg} was previously downloaded in {apps_path}, outside miniforge, but no module was created.\nContent of {apps_path}:\n{installib.contentFolder(apps_path)}\nDo you want to proceed? [y/N]: "
            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit(1)

    if input("Is this running in a screen process? [y/N]: ").strip().lower() not in ["y", "yes"]:
        print(f"Take note in which node you're located, then run: screen -S {main_pkg}_python")
        sys.exit(0)

    # Create screen process for the actual install
    node = input("In which node are you running the install?: ")
    input(f"Create a screen process for the actual install: screen -S {main_pkg}_install [Enter]")

    if create_env:
        if micro:
            default_py = f"{major}.{minor}.{micro}"
        else:
            default_py = f"{major}.{minor}"

        venv_python = input(f"\nWhat python version is required by {main_pkg}/{version} (i.e. python>=3.10, python=3.13. [Enter] if no specific version required): ") or f"python={default_py}"
        if (not venv_python.startswith("python=")) and (not venv_python.startswith("python>")):
            venv_python = f"python={venv_python}"
        input(f"\nconda create -n {env_name} {venv_python} [Enter]")
        input(f"conda env list | grep {env_name} [Enter]")

    if os.path.isdir(forge_dir):
        input(f"\nconda activate {env_name} [Enter]")
    else:
        print(f"Conda dir was not created: {forge_dir}")
        sys.exit(1)

    # Clone git repos if applicable
    git_dirs = installib.cloneRepos(main_pkg, version)

    if input("\nDo you need to run any pip installs? [y/N]: ").strip().lower() in ["y", "yes"]:
        which_pip = input("\nrun 'which pip' and paste here the output: ")
        if which_pip!=f"{forge_path}/pip":
            input(f"*** DO NOT PROCEED UNTIL YOU THE RESULT OF 'which pip' IS {forge_path}/pip *** [Enter]")

        print("\nAfter each pip install run 'conda list | grep <program>' to check that it was indeed installed, and run any tests.\nDo not proceed with the next dependency until the previous one is installed and tested.\nRemember to add the version of each dependency if a specific version is needed!\n")
        pips = input("List of programs to install using pip divided by comma: ").strip().split(",")
        for pip_install in pips:
            input(f"pip install {pip_install} [Enter]")
            input(f"conda list | grep {pip_install} [Enter]")
            input(f"Run a test command for {pip_install} [Enter]")

    if input("\nDo you need to run any 'conda install' commands? [y/N]: ").strip().lower() in ["y", "yes"]:
        print("Don't do Ctrl-C after you hit proceed! That will not do a clean end and will corrupt the environment!")
        print("Check each conda install with 'conda list | grep <pkg>'")
        input(f"i.e. conda list | grep {main_pkg} [Enter]")

    # If I need to install a kernel for jupyter
    if input("\nIs this program going to be run from Jupyter Notebook? [y/N]: "):
        input("conda install ipykernel [Enter]")
        input("Create kernel from one of the others: /hpc/apps/miniforge/share/jupyter/kernels [Enter]")

    # Run tests with the conda environment activated
    print("\nTest the conda environment:")

    msg = f"The list of commands for {main_pkg} can be found in {forge_path}."
    if os.path.isdir(f"{apps_path}/{version}/bin"):
        msg+=f" And in {apps_path}/{version}/bin."
    input(f"{msg}. [Enter]")

    input(f"\nconda deactivate [Enter]")

    # Download databases
    db_env_var = ""
    if input("\nDo you need to download any databases? [y/N]: ").strip().lower() in ("yes", "y"):
        Path(db_folder).mkdir(parents=True, exist_ok=True)
        input(f"Download any databases to {db_folder} [Enter]")
        db = input("Name of the environment variable that the program requires to point to the DB path: ")
        if db:
            db_env_var = db

    # Create module file
    if not installib.createMdlFile(main_pkg, version, forge_path, True, git_dirs, db_env_var, db_folder):
        input(f"Create {new_ml} manually [Enter]")

    # Check module file
    print("\nCompare new module file with another one that also uses conda:")
    returncode, stderr, stdout = installib.runBash(["bash", "-lc", "grep -r conda /hpc/modulefiles | tail -n 1 | cut -d: -f1"])
    if returncode!=0:
        print(f"vi /hpc/modulefiles/{stdout}")
    input(f"vi {new_ml} [Enter]")

    # Test final module
    print(f"\nAvailable packages for {main_pkg}:")
    input(f"ml avail {main_pkg} [Enter]")
    print(f"\nModule information:")
    input(f"ml show {main_pkg}/{version} [Enter]")

    # Run final tests
    print("\nTest the final module:")
    input(f"The list of commands for {main_pkg} can be found in {forge_path}. [Enter]")

    tests = input(f"Input file with the list of tests that you would like to run ([Enter] if no specific tests): ").strip()
    try:
        with open(tests, "r") as fin:
            line = fin.readline()
            input(f"{line} [Enter]")
    except Exception as e:
        print(f"WARNING: could not read {tests}: {e}")

    # Close screen processes
    input(f"Login to {node} as root [Enter]")
    input(f"screen -S {main_pkg}_install -X quit [Enter]")
    print(f"*** Remember to kill this screen process: screen -S {main_pkg}_python -X quit ***")

if __name__ == "__main__":
    main()