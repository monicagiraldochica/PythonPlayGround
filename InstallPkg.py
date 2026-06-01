#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install modules with make"

import sys
import argparse
import installib
import os
from pathlib import Path
import shutil

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install a new module using make")
    parser.add_argument("--mdl-name", help="Name of the new module", required=True)
    parser.add_argument("--mdl-vers", help="Version of the new module", required=True)
    parser.add_argument("--pkg-url", help="URL to download the package", required=True)

    parser.add_argument("--download-in-apps", action="store_true", help="Download in apps folder instead of builds")
    parser.add_argument("--compile", action="store_true", help="Package needs to be compiled")

    args = parser.parse_args()

    mdl_name = args.mdl_name
    download_in_apps = args.download_in_apps or mdl_name=="afni"

    return mdl_name, args.mdl_vers, download_in_apps, args.pkg_url, args.compile

def main():
    # Check python version
    if not installib.checkPythonVers(3, 7)[0]:
        print("ERROR: This script requires Python 3.7 or higher\n")
        sys.exit(1)

    # Make sure I'm root in a login node
    input("\nssh into login node [Enter]")
    input("sudo su - [Enter]")

    mdl_name, mdl_vers, download_in_apps, pkg_url, compile = parse_arguments()

    if input("Is this running in a screen process? [y/N]: ").strip().lower() not in ["y", "yes"]:
        print(f"Take note in which node you're located, then run: screen -S {mdl_name}_python")
        sys.exit(0)

    if (not pkg_url.startswith("https://")) and (not pkg_url.startswith("http://")):
        pkg_url = "https://"+pkg_url
    git = pkg_url.startswith("https://github.com")

    msg1 = "Thanks for the request. Since this software expects to read and write within its own installation directory, " \
        "it doesn't fit well with our centrally managed, read-only software environment on the cluster. " \
        "A good option is to install it in your scratch space where you have full write access, " \
        "and then update your Slurm job scripts to cd into that directory before running it. " \
        "This should allow it to run as intended without permission issues. Let us know if you'd like any help setting that up.\n\n" \
        "Thanks, RCC"
    
    # Check if the module was already installed
    ml_avail = installib.availableModules(mdl_name)

    # The module is already installed
    if f"{mdl_name}/{mdl_vers}" in ml_avail:
        print(f"\nGood news! {mdl_name}/{mdl_vers} is already installed!")
        sys.exit(1)

    # A different version of the module was installed
    elif len(ml_avail)>0:
        if input(f"\nA different version of {mdl_name} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {mdl_name}/{mdl_vers}? [y/N]: ").strip().lower() not in ("yes", "y"):
            sys.exit(1)

    # Check that the software can run in the cluster before download if possible
    if git and (not compile) and input("Can the script run from any location? [Y/n]").strip().lower() not in ["n", "no"]:
        print(f"ERROR: This program can't be installed centrally as a module. Send the user the following message:/n/n{msg1}")
        sys.exit(1)

    # Check that the repository wasn't already downloaded, otherwise, download and unzip if needed
    app_path = f"/hpc/apps/{mdl_name}/{mdl_vers}"
    download_dir = app_path if download_in_apps else f"/adminfs/builds/{mdl_name}/{mdl_vers}"
    if os.path.isdir(download_dir):
        print(f"{download_dir} already exists, skipping this download.")
    else:    
        returncode, stderr, stdout, download_dir, compile = installib.downloadPackage(download_in_apps, pkg_url, mdl_name, mdl_vers)    
        if returncode!=0:
            err = (stderr or stdout or "").strip()
            print(f"ERROR: could not download {mdl_name}: {err}")
            sys.exit(1)
        print(f"Package successfully downloaded to {download_dir}")
        
    req_file = f"{download_dir}/requirements.txt"
    msg2 = f"A requirement file exists in this repository: {req_file}. " \
        "You need to check that all the requirements are present in an existing python module. " \
        "If not, this module needs to be created as a conda environment. " \
        "To check each package, run (after activating a python module): python3 -c 'import <module_name>'"
    required_modules = []

    # Check that the software can run in the cluster
    if (not git) and (not compile) and input("Can the script run from any location? [Y/n]").strip().lower() not in ["n", "no"]:
        print(f"ERROR: This program can't be installed centrally as a module. Send the user the following message:/n/n{msg1}")
        sys.exit(1)
    
    elif git and os.path.isfile(req_file):
        print(msg2)
        req_py = input("Input the python module that contains all the requirements (Enter if none found): ")
        if not req_py:
            print(f"ERROR: You need to create this module as a conda environment. Run: python3 createMiniforgeModule.py --main-pkg {mdl_name} --version {mdl_vers}")
            sys.exit(1)
        required_modules+=[req_py]

        if input("\nIs this program going to be run from Jupyter Notebook? [y/N]: "):
            input("Create kernel from one of the others: /hpc/apps/miniforge/share/jupyter/kernels [Enter]")

    if compile:
        os.chdir(download_dir)
        if not os.path.isfile("configure"):
            print(f"ERROR: No configure file found in {download_dir}. Can't compile.")
            sys.exit(1)
        input(f"cd {download_dir}")

        # Load the necessary modules
        ml_load = []
        for mdl in ["openmpi", "cuda"]:
            if input(f"Does {mdl_name} uses {mdl} [y/N]? ").strip().lower() in ["y", "yes"]:
                avail = installib.availableModules(mdl)
                if (not avail) and (input(f"{mdl} not available. Do you want to proceed? [y/N]").strip().lower() not in ["y", "yes"]):
                    print(f"ERROR: {mdl} not available. Can't compile.")
                    sys.exit(1)
                ml_load.append(avail[-1])

        latest = ""
        for mdl in ["cmake", "gcc"]:
            avail = installib.availableModules(mdl)
            if not avail:
                print(f"ERROR: {mdl} not available. Can't compile.")
                sys.exit(1)
            latest = avail[-1]
            ml_load.append(latest)

        input(f"ml load {' '.join(ml_load)} [Enter]")

        # Set the correct environment variables for compilation
        input("CC=/hpc/apps/gcc/<version>/bin/gcc [Enter]")
        input("CXX=/hpc/apps/gcc/<version>/bin/g++ [Enter]")

        # Compile
        node = input("In which node are you running the install?: ")
        input(f"screen -S {mdl_name}_install [Enter]")
        input(f'./configure --prefix {app_path} LDFLAGS="-Wl,-rpath,/hpc/apps/{latest}/lib64" [Enter]')
        input("make -j 4 [Enter]")
        input("make install")

    # Run Tests
    input(f"cd {app_path}/bin [Enter]")
    input("Test an executable in that directory [Enter]")

    # Download DB if needed
    db_env_var = ""
    if input("\nDo you need to download any databases? [y/N]: ").strip().lower() in ("yes", "y"):
        db_folder = f"/hpc/refdata/{mdl_name}"
        Path(db_folder).mkdir(parents=True, exist_ok=True)
        input(f"Download any databases to {db_folder} [Enter]")
        db = input("Name of the environment variable that the program requires to point to the DB path: ")
        if db:
            db_env_var = db

    # Clone git repos if applicable
    git_dirs = installib.cloneRepos(mdl_name, mdl_vers)

    # Create module file
    new_ml = f"/hpc/modulefiles/{mdl_name}/{mdl_vers}.lua"
    if not installib.createMdlFile(mdl_name, mdl_vers, f"{app_path}/bin", False, git_dirs, db_env_var, db_folder, required_modules):        
        input(f"Create {new_ml} manually [Enter]")

    # Check module file
    input(f"vi {new_ml} [Enter]")

    # Check module file
    print("\nCompare new module file with another one that also uses conda:")
    returncode, stderr, stdout = installib.runBash(["bash", "-lc", "grep -r conda /hpc/modulefiles | tail -n 1 | cut -d: -f1"])
    if returncode!=0:
        print(f"vi /hpc/modulefiles/{stdout}")
    input(f"vi {new_ml} [Enter]")

    # Test final module
    print(f"\nAvailable packages for {mdl_name}:")
    input(f"ml avail {mdl_name} [Enter]")
    print(f"\nModule information:")
    input(f"ml show {mdl_name}/{mdl_vers} [Enter]")

    # Run final tests
    print("\nTest the final module:")
    input(f"The list of commands for {mdl_name} can be found in {app_path}/bin. [Enter]")

    tests = input(f"Input file with the list of tests that you would like to run ([Enter] if no specific tests): ").strip()
    try:
        with open(tests, "r") as fin:
            line = fin.readline()
            input(f"{line} [Enter]")
    except Exception as e:
        print(f"WARNING: could not read {tests}: {e}")

    # Remove from builds if desired
    if not download_in_apps:
        print(f"Content of {download_dir}:\n{installib.contentFolder(download_dir)}")
        if input(f"Do you want to remove {download_dir}? [Y/n]: ") not in ["y", "yes"]:
            shutil.rmtree(download_dir)
            parent_dir = os.path.dirname(download_dir)
            try:
                os.rmdir(parent_dir)
            except OSError as e:
                if "not empty" not in str(e).lower():
                    print(f"WARNING: could not delete {parent_dir}")

    # Close screen processes
    input(f"Login to {node} as root [Enter]")
    input(f"screen -S {mdl_name}_install -X quit [Enter]")
    print(f"*** Remember to kill this screen process: screen -S {mdl_name}_python -X quit ***")

if __name__ == "__main__":
    main()