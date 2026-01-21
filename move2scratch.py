#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Copy files to scratch before submission"

import argparse
import sys
import os
from typing import List
import getpass
import grp
import shutil

def parse_args():
    """Parse command-line arguments and return them."""
    parser = argparse.ArgumentParser(description="Script to copy files to scratch before submitting a job.")
    parser.add_argument("--list", type=str, required=True, help="Path to .txt file with the list of input files/folders.")
    parser.add_argument("--slurm", type=str, required=True, help="Path to the SLURM script.")
    parser.add_argument("--output-dir", type=str, required=False, 
                        help="Path to target directory in scratch.\n"
                            "If not provided, the default will be:\n"
                            "/scratch/g/group/user/script_name"
                        )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files without asking.")
    
    return parser.parse_args()

def readInputFiles(input_list: str) -> List[str]:
    """Read list of input files."""
    # Perform checks
    if not input_list.endswith(".txt"):
        raise Exception(f"Invalid file type: '{input_list}'. Only .txt files are allowed.")

    if not os.path.exists(input_list):
        raise FileNotFoundError(f"File '{input_list}' does not exist.")

    # Read file
    paths = []
    with open(input_list, "r") as f:
        for line in f:
            path = line.strip()
            if not path:
                continue

            if not os.path.exists(path):
                raise FileNotFoundError(f"Path '{path}' does not exist.")
            
            paths.append(path)

    return paths

def checkJobName(jobName: str) -> bool:
    return True

def checkScript(script: str) -> bool:
    """Check SLURM script."""
    if not os.path.exists(script):
        raise FileNotFoundError(f"File '{script}' does not exist.")

    with open(script, "r") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("#SBATCH"):
                continue

            if line.startswith("#SBATCH --job-name=") and not checkJobName(line.replace("#SBATCH --job-name=","")):
                print(f"Bad job name in line: {line}.")
                return False

    return True

def computeSize(path):
    """
    Returns size of path in GB
    """
    if os.path.isfile(path):
        return os.path.getsize(path) / 1_000_000_000
    
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total / 1_000_000_000

def copyFiles(input_files: List[str], output_dir: str, force: bool):
    for src in input_files:
        basename = os.path.basename(src)
        dest = os.path.join(output_dir, basename)

        if os.path.isfile(src) and os.path.exists(dest):
            if os.path.isfile(dest) and not force and input(f"{dest} already exists. Overwrite? [y/N] ")!='y':
                print(f"Skipping {src}")
                continue

            elif os.path.isdir(dest):
                print(f"Cannot override directory {dest} with file {src}.")
                continue

        size = computeSize(src)
        if size>=25 and size<100 and input(f"You are about to copy {size}GB to scratch. Continue? [y/N] ")!='y':
            print(f"Skipping {src}")
            continue
        if size>=100:
            print(f"The size of {src} is {size}GB. That's too large, skipping {src}.")
            continue
            
        if os.path.isdir(src):
            shutil.copytree(src, dest, dirs_exist_ok=True)

        else:
            shutil.copy2(src, dest)

def validateOutputDir(output_dir: str, slurm_script: str) -> str:
    """
    Validates or creates the scratch output directory.
    Must be in the user' group scratch.
    If no path is provided or the path is not in the user' group scratch, uses the default.
    """

    user = getpass.getuser()
    print(f"Your username is {user}.")
    gid = os.getgid()
    group = grp.getgrgid(gid).gr_name
    print(f"Your group is {group}.")

    default_base = f"/scratch/g/{group}"
    if not os.path.isdir(default_base):
        raise Exception(f"Scratch group directory missing: '{default_base}'.")
    
    try:
        if not output_dir or not output_dir.startswith(default_base):
            default_user_dir = os.path.join(default_base, user)
            os.makedirs(default_user_dir, exist_ok=True)

            script_name = os.path.splitext(os.path.basename(slurm_script))[0]
            default_job_dir = os.path.join(default_user_dir, script_name)
            os.makedirs(default_job_dir, exist_ok=True)

            return default_job_dir
        
        else:
            os.makedirs(output_dir, exist_ok=True)
            return output_dir

    except PermissionError as e:
        raise Exception("Permission denied creating output directory: {e}")
    
    except OSError as e:
        raise Exception(f"Error creating directory output directory: {e}")

def main():
    try:
        args = parse_args()
        input_list = args.list
        slurm_script = args.slurm
        output_dir = validateOutputDir(args.output_dir, slurm_script)
        input_files = readInputFiles(input_list)

        if not input_files:
            raise Exception(f"No valid paths found in input file '{input_list}'.")

        if not checkScript(slurm_script):
            raise Exception("SLURM script has errors.")
        
        if not os.path.isdir(output_dir):
            raise FileNotFoundError(f"'{output_dir}' is not a directory.")
        
        copyFiles(input_files, output_dir, args.force)

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
