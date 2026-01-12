#!/usr/bin/env python3
import argparse
import sys
import os

# Functions
def parse_args():
    """Parse command-line arguments and return them."""
    
    parser = argparse.ArgumentParser(description="Script to copy files to scratch before submitting a job")
    parser.add_argument("--list", type=str, required=True, help="Path to .txt file with the list of input files/folders")
    parser.add_argument("--slurm", type=str, required=True, help="Path to the SLURM script")
    return parser.parse_args()

def readInputFiles(input_list):
    """Read list of input files."""
    
    # Perform checks
    if not input_list.endswith(".txt"):
        raise ValueError(f"Invalid file type: '{input_list}'. Only .txt files are allowed")

    if not os.path.exists(input_list):
        raise FileNotFoundError(f"File '{input_list}' does not exist")

    # Read file
    paths = []
    with open(filename, "r") as f:
        for line in f:
            path = line.strip()
            if not path:
                continue

            if not os.path.exists(path):
                raise FileNotFoundError(f"Path '{path}' does not exist")
            paths.append(path)

    return paths

# Main script
def main():
    args = parse_args()
    input_list = args.list
    slurm_script = args.slurm

    try:
        input_files = readInputFiles(input_list)

    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Unexpected ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
1. File and I/O Exceptions
FileNotFoundError → file does not exist
IsADirectoryError → expected a file but got a directory
PermissionError → lack permission to read/write/execute
IOError / OSError → generic I/O or OS errors

2. Value and Type Errors
ValueError → invalid value (e.g., converting "abc" to int)
TypeError → wrong type for an operation (e.g., adding int + str)
IndexError → list/tuple index out of range
KeyError → dictionary key not found

3. Control Flow and Iteration
StopIteration → iterator has no more elements
GeneratorExit → generator is closed

4. Arithmetic
ZeroDivisionError → division by zero
OverflowError → result too large for a numeric type

5. Import and Name Errors
ImportError / ModuleNotFoundError → module cannot be imported
NameError → variable is not defined

6. Attribute and Syntax Errors
AttributeError → object does not have that attribute/method
SyntaxError → invalid Python syntax
IndentationError → bad indentation

7. Others
MemoryError → system ran out of memory
NotImplementedError → abstract method not implemented
RuntimeError → generic runtime problem
AssertionError → failed assert statement
You can also create your own custom exceptions by subclassing Exception if you want more descriptive, domain-specific errors in your programs.
"""
