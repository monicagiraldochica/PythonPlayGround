#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Copy files to scratch before submission"

import argparse
import sys
import os
from typing import List

# Functions
def parse_args():
    """Parse command-line arguments and return them."""
    
    parser = argparse.ArgumentParser(description="Script to copy files to scratch before submitting a job")
    parser.add_argument("--list", type=str, required=True, help="Path to .txt file with the list of input files/folders")
    parser.add_argument("--slurm", type=str, required=True, help="Path to the SLURM script")
    return parser.parse_args()

def readInputFiles(input_list: str) -> List[str]:
    """Read list of input files."""
    
    # Perform checks
    if not input_list.endswith(".txt"):
        raise ValueError(f"Invalid file type: '{input_list}'. Only .txt files are allowed")

    if not os.path.exists(input_list):
        raise FileNotFoundError(f"File '{input_list}' does not exist")

    # Read file
    paths = []
    with open(input_list, "r") as f:
        for line in f:
            path = line.strip()
            if not path:
                continue

            if not os.path.exists(path):
                raise FileNotFoundError(f"Path '{path}' does not exist")
            paths.append(path)

    return paths

def checkJobName(jobName: str) -> bool:
    return True

def checkScript(script: str) -> bool:
    """Check SLURM script."""

    if not os.path.exists(script):
        raise FileNotFoundError(f"File '{script}' does not exist")

    with open(script, "r") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("#SBATCH"):
                continue

            if line.startswith("#SBATCH --job-name=") and not checkJobName(line.replace("#SBATCH --job-name=","")):
                print(f"Bad job name in line: {line}")
                return False

    return True

# Main code
def main():
    args = parse_args()
    input_list = args.list
    slurm_script = args.slurm

    try:
        input_files = readInputFiles(input_list)
        if not input_files:
            raise ValueError(f"No valid paths found in input file '{input_list}'")

        if not checkScript(slurm_script):
            raise Exception("SLURM script has errors")

    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
