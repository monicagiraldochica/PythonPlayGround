#!/usr/bin/env python3
__author__ = "Monica Keith"
__purpose__ = "Common functions to install modules in the cluster"

import subprocess
from typing import Sequence
import sys
from pathlib import Path
import os
import re

def runBash(cmd: Sequence[str], output_file:str=None):
    file_handle = None
    try:
        if output_file:
            file_handle = open(output_file, "w")
        stdout_target = file_handle if output_file else subprocess.PIPE

        # text=True: makes stdout and stderr strings instead of bytes
        # check=True: if there's an error, an exception is produced
        result = subprocess.run(cmd, stdout=stdout_target, stderr=subprocess.PIPE, text=True, check=True)
        stdout = "" if output_file else result.stdout
        return result.returncode, result.stderr, stdout
    
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e)).strip()
        return e.returncode, err, ""
    
    finally:
        if file_handle:
            file_handle.close()

def checkPythonVers(req_major=0, req_minor=0, req_micro=0):
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    print(f"Python version: {major}.{minor}.{micro}")

    if major<req_major or minor<req_minor or micro<req_micro:
        return False, major, minor, micro
    return True, major, minor, micro

def downloadPackage(download_in_apps: bool, pkg_url: str, mdl_name: str, mdl_vers: str, git:False):
    download_dir = f"/hpc/apps/{mdl_name}/{mdl_vers}" if download_in_apps else f"/adminfs/builds/{mdl_name}/{mdl_vers}"

    # Create and navigate to the download directory
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(download_dir)

    # Download and unzip package
    if git:
        returncode, stderr, stdout = runBash(["git clone", pkg_url])

    else:
        returncode, stderr1, stdout1 = runBash(["wget", pkg_url])
        if returncode==0:
            returncode, stderr2, stdout2 = decompress(pkg_url.rsplit("/", 1)[-1])
        stderr = stderr1+stderr2
        stdout = stdout1+stdout2

    return returncode, stderr, stdout, download_dir

# Returns returncode, stderr, stdout
def decompress(filename: str):
    if filename.endswith(".rpm"):
        cmd = f"rpm2cpio {filename} | cpio -idv"
        return runBash(["bash", "-lc", cmd])
    
    elif filename.endswith(".zip"):
        return runBash(["unzip", filename])
    
    elif filename.endswith(".tgz") or filename.endswith(".tar.gz"):
        return runBash(["tar", "-xvzf", filename])
    
    elif filename.endswith(".tar.bz2"):
        return runBash(["tar", "xvfj", filename])
    
    elif filename.endswith(".tar.xz"):
        return runBash(["tar", "xf", filename])
    
    elif filename.endswith(".gz"):
        return runBash(["gzip", "-dk", filename])
    
    else:
        return 2, f"Dont know how to extract {filename}", ""

def availableModules(pkg: str):
    lmod_cmd = os.environ.get("LMOD_CMD")
    if not lmod_cmd:
        print("Error: LMOD_CMD is not set; Lmod is not initialized")
        return []
    
    returncode, stderr, stdout = runBash([lmod_cmd, "shell", "avail", pkg])    
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Error: Could not check available modules for {pkg}: {err}")
        return []

    if f"{pkg}/" in stdout:
        txt = stdout
    elif f"{pkg}/" in stderr:
        txt = stderr
    else:
        return []
    return re.findall(rf'\b{re.escape(pkg)}/[^\s]+', txt)