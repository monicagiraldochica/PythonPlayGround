#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install modules with make"

import sys
import argparse
import installib
import logging
import os

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install a new module using make)")
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
        logging.error("This script requires Python 3.7 or higher\n")
        sys.exit(1)

    # Make sure I'm root in a login node
    input("\nssh into login node [Enter]")
    input("sudo su - [Enter]")

    mdl_name, mdl_vers, download_in_apps, pkg_url = parse_arguments()
    if (not pkg_url.startswith("https://")) and (not pkg_url.startswith("http://")):
        pkg_url = "https://"+pkg_url
    git = pkg_url.startswith("https://github.com")

    msg1 = "Thanks for the request. Since this software expects to read and write within its own installation directory, " \
        "it doesn't fit well with our centrally managed, read-only software environment on the cluster. " \
        "A good option is to install it in your scratch space where you have full write access, " \
        "and then update your Slurm job scripts to cd into that directory before running it. " \
        "This should allow it to run as intended without permission issues. Let us know if you’d like any help setting that up.\n\n" \
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
        logging.error(f"This program can't be installed centrally as a module. Send the user the following message:/n/n{msg1}")
        sys.exit(1)

    # Check that the repository wasn't already downloaded, otherwise, download and unzip if needed
    download_dir = f"/hpc/apps/{mdl_name}/{mdl_vers}" if download_in_apps else f"/adminfs/builds/{mdl_name}/{mdl_vers}"
    if os.path.isdir(download_dir):
        print(f"{download_dir} already exists, skipping this download.")
    else:    
        returncode, stderr, stdout, download_dir, compile = installib.downloadPackage(download_in_apps, pkg_url, mdl_name, mdl_vers)    
        if returncode!=0:
            err = (stderr or stdout or "").strip()
            logging.error(f"Error downloading {mdl_name}: {err}")
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
        logging.error(f"This program can't be installed centrally as a module. Send the user the following message:/n/n{msg1}")
        sys.exit(1)
    
    elif git and os.path.isfile(req_file):
        print(msg2)
        req_py = input("Input the python module that contains all the requirements (Enter if none found): ")
        if not req_py:
            logging.error(f"You need to create this module as a conda environment. Run: python3 createMiniforgeModule.py --main-pkg {mdl_name} --version {mdl_vers}")
            sys.exit(1)
        required_modules+=[req_py]

        if input("\nIs this program going to be run from Jupyter Notebook? [y/N]: "):
            input("Create kernel from one of the others: /hpc/apps/miniforge/share/jupyter/kernels [Enter]")

    # Compile
    #openmpi = availableModules

    # Test in /hpc/apps/app/bin

    # Download DB if needed

    # Create lua file (hidden module), add required_modules if any

    # Test

    # Make module visible

    # Remove from builds if desired

    # Specific software

if __name__ == "__main__":
    main()