#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install modules with make"

import sys
import argparse
from pathlib import Path
import os
import installib

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install a new module using make)")
    parser.add_argument("--mdl-name", help="Name of the new module", required=True)
    parser.add_argument("--mdl-vers", help="Version of the new module", required=True)
    parser.add_argument("--pkg-url", help="URL to download the package", required=True)

    parser.add_argument("--download-in-apps", action="store_true", help="Download in apps folder instead of builds")

    args = parser.parse_args()

    mdl_name = args.mdl_name
    dia = args.download_in_apps or mdl_name=="afni"

    return [mdl_name, args.mdl_vers, dia, args.pkg_url]

def main():
    if input("Are you sudo in a login node? [Y/n]").strip().lower() not in ["n", "no"]:
        print("You must be sudo in a login node")
        sys.exit(1)

    [mdl_name, mdl_vers, dia, pkg_url] = parse_arguments()

    # Create and navigate to the download directory
    install_dir = f"/hpc/apps/{mdl_name}/{mdl_vers}"
    download_dir = install_dir if dia else f"/adminfs/builds/{mdl_name}/{mdl_vers}"
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(download_dir)

    # Download and unzip package
    [returncode, stderr, stdout] = installib.runBash(["wget", pkg_url])
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Error downloading {mdl_name}: {err}")
        sys.exit(1)

    filename = pkg_url.rsplit("/", 1)[-1]
    if filename.endswith(".rpm"):
        cmd = f"rpm2cpio {filename} | cpio -idv"
        [returncode, stderr, stdout] = installib.runBash(["bash", "-lc", cmd])
    elif filename.endswith(".zip"):
        [returncode, stderr, stdout] = installib.runBash(["unzip", filename])
    elif filename.endswith(".tgz") or filename.endswith(".tar.gz"):
        [returncode, stderr, stdout] = installib.runBash(["tar", "-xvzf", filename])
    elif filename.endswith(".tar.bz2"):
        [returncode, stderr, stdout] = installib.runBash(["tar", "xvfj", filename])
    elif filename.endswith(".tar.xz"):
        [returncode, stderr, stdout] = installib.runBash(["tar", "xf", filename])
    elif filename.endswith(".gz"):
        [returncode, stderr, stdout] = installib.runBash(["gzip", "-dk", filename])
    else:
        [returncode, stderr, stdout] = [2, f"Dont know how to extract {filename}", ""]
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Error downloading {mdl_name}: {err}")
        sys.exit(1)

    # Compile

    # Test in /hpc/apps/app/bin

    # Download DB if needed

    # Create lua file (hidden module)

    # Test

    # Make module visible

    # Remove from builds if desired

    # Specific software

if __name__ == "__main__":
    main()