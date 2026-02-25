#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install Perl packages"

import subprocess
import sys
import os
import argparse
import re

def check_module(mdl: str) -> int:
    """
    Check if a Perl module is installed.
    Returns:
    0 -> Module installed
    1 -> Module not installed
    2 -> Compilation/runtime errors
    """
    try:
        is_dispatcher = mdl.startswith("Log::Report::Dispatcher")

        cmd = f"perl -M{mdl} -e print 'Installed'\n"
        print(f"Running: {cmd}...\n")
        # capture_output=True: do NOT print the command's output to the terminal
        # text=True: makes stdout and stderr strings instead of bytes
        # check=True: if there's an error, an exception is produced
        result = subprocess.run(cmd, capture_output=True, text=True) if is_dispatcher else subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode==0 and result.stdout.strip()=="Installed":
            return 0
        
        elif is_dispatcher:
            cmd = f"perl -e use Log::Report (); require {mdl}; print 'Installed'\n"
            print(f"Running: {cmd}...\n")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.returncode==0 and result.stdout.strip()=="Installed":
                return 0

        err = (result.stderr or result.stdout or "").strip()
        if re.search(r"^Can't locate .* in \@INC\b", err, flags=re.M):
            return 1
        
        print(f"{err}\n")
        return 2

    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e)).strip()
        print(f"{err}\n")
        return 2

def loop(missing_modules, install, success_out="success.txt", fail_out="fail.txt"):
    dic1 = {0:[], 1:[], 2:[]}
    dic2 = {
        0: "installed",
        1: "not installed",
        2: "had compilation/runtime errors",
    }
    dic3 = {}

    for mdl in missing_modules:
        status = check_module(mdl)

        if status==1 and install:
            print(f"Installing {mdl}")

            try:
                cmds = [f"cpan -T{mdl}", f"cpanm -T{mdl}"]
                for i in range(1):
                    cmd = cmds[i]
                    print(f"\nRunning: {cmd}...")

                    if i==1:
                        # capture_output=True: do NOT print the command's output to the terminal
                        # text=True: makes stdout and stderr strings instead of bytes
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode==0:
                            break
                    else:
                        # check=True: if there's an error, an exception is produced
                        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        err = (result.stderr or result.stdout or "").strip()
                        dic3[mdl] = f"Unexpected error installing {mdl}: {err}"

            except subprocess.CalledProcessError as e:
                err = (e.stderr or e.stdout or str(e)).strip()
                dic3[mdl] = f"Unexpected error installing {mdl}: {err}"
            
            status = check_module(mdl)

        dic1[status].append(mdl)

    if (not install):
        try:
            if dic1[0]:
                with open(success_out, "w") as fout:
                    for mdl in dic1[0]:
                        fout.write(f"{mdl}\n")

            with open(fail_out, "w") as fout:
                # Save modules that failed previously
                for status,msg in dic2.items():
                    if status>0:
                        for mdl in dic1[status]:
                            fout.write(f"{mdl} {msg}\n")
                
                # Save modules that failed in this run
                for mdl,msg in dic3.items():
                    fout.write(f"{mdl} {msg}\n")
        
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise RuntimeError(f"File operation failed: {e}") from e

    else:
        if dic3.items():
            print("\nFailed in current run:")
        for mdl,msg in dic3.items():
            print(f"{mdl}: {msg}\n")

        if dic2.items() and dic3.items():
            print("\nOther:")
        for status,msg in dic2.items():
            if dic1[status]:
                list_txt = "\n\t".join(dic1[status])
                print(f"{msg}:\n\t{list_txt}")

def txt2dic(txt, working_dir):
    """
    Read a tab-delimited file into a dict {key: value}.
    Skips blank lines and lines without at least 2 columns.
    """
    try:
        dic = {}
        output = f"{working_dir}/{txt}"
        with open(output, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.split("\t")
                if len(line)>=2:
                    dic[line[0]] = line[1]

    except FileNotFoundError:
        raise RuntimeError(f"File not found: {output}")

    except PermissionError:
        raise RuntimeError(f"No permission to read: {output}")

    except UnicodeDecodeError:
        raise RuntimeError(f"File is not valid UTF-8: {output}")

    except OSError as e:
        raise RuntimeError(f"Unexpected OS error when opening {output}: {e}")

    return dic

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install Perl packages on the cluster")
    parser.add_argument("--working-dir", help="Directory where outputs will be saved", required=True)
    parser.add_argument("--vnew", help="New Perl version")
    parser.add_argument("--vold", help="Old Perl version")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--migrate", action="store_true", help="Install all vold packages in vnew")
    group.add_argument("--install", help="package(s) to install in vnew, divided by comma")

    args = parser.parse_args()
    
    v_new = args.vnew or "5.42.0"
    v_old = args.vold or "5.26.1"

    working_dir = args.working_dir
    if not os.path.isdir(working_dir):
        sys.exit(f"{working_dir} doesn't exist")
    working_dir = working_dir[:-1] if working_dir.endswith("/") else working_dir
    
    return [v_new, v_old, args.migrate, args.install, working_dir]

def get_perl_version():
    try:
        v = subprocess.check_output(["perl", "-e", "print $^V"], text=True).strip()
        return v.lstrip("v")
    
    except FileNotFoundError:
        return None
    
    except subprocess.CalledProcessError:
        return None

def main():
    # Check python version
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    if major==0 or minor==0 or major<3 or minor<7:
        print(f"Python version: {major}.{minor}.{micro}\nThis script requires Python 3.7 or higher.")
        sys.exit(1)

    [v_new, v_old, migrate, install, working_dir] = parse_arguments()

    # Check perl version
    perl_version = get_perl_version()
    if perl_version is None:
        print("Perl module is not loaded")
        sys.exit(1)
    elif perl_version!=v_new:
        print(f"Wrong perl version loaded ({perl_version}). Need {v_new}")
        sys.exit(1)

    if migrate:
        try:
            # Put the list of modules from the new version in dictionary
            dic_new = txt2dic(f"{v_new}.txt", working_dir)

            # Put the list of modules from the old version in dictionary
            dic_old = txt2dic(f"{v_old}.txt", working_dir)

            # Get the list of missing packages
            missing_keys = set(dic_old.keys()) - set(dic_new.keys())

            # Install missing modules
            loop(missing_keys, True)

            # Check installs
            loop(missing_keys, False)

        except Exception as err:
            print(f"Fatal error: {err}")
            sys.exit(1)

    if install:
        loop(install.split(","), True)         

if __name__ == "__main__":
    main()
