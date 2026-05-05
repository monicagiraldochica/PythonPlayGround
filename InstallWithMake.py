#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install Perl packages"

import sys
import argparse
from pathlib import Path
import os

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install a new module using make)")
    parser.add_argument("--mdl-name", help="Name of the new module", required=True)
    parser.add_argument("--mdl-vers", help="Version of the new module", required=True)
    parser.add_argument("--download-in-apps", action="store_true", help="Download in apps folder instead of builds")
    args = parser.parse_args()

    mdl_name = args.mdl_name
    dia = args.download_in_apps or mdl_name=="afni"

    return [mdl_name, args.mdl_vers, dia]

def main():
    if input("Are you sudo in a login node? [Y/n]").strip().lower() not in ["n", "no"]:
        print("You must be sudo in a login node")
        sys.exit(1)

    [mdl_name, mdl_vers, dia] = parse_arguments()

    # Create and navigate to the download directory
    install_dir = f"/hpc/apps/{mdl_name}/{mdl_vers}"
    download_dir = install_dir if dia else f"/adminfs/builds/{mdl_name}/{mdl_vers}"
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(download_dir)

if __name__ == "__main__":
    main()