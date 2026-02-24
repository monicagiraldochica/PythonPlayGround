#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install Perl packages"

import subprocess
import sys
import os
import argparse

def check_module(mdl: str) -> int:
    """
    Check if a Perl module is installed.
    Returns:
    0 -> Module installed
    1 -> Module not installed
    2 -> Module can't be located
    """
    try:
        result = subprocess.run(['perl', f"-M{mdl}", '-e', 'print "Installed\n"'], capture_output=True, text=True, check=True)
        return 0 if result.stdout.strip()=="Installed" else 1

    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or str(e)).strip()
        if "Can't locate" in msg:
            return 2 # missing module
        else:
            return 3 # any other Perl compilation/runtime error

def loop(missing_modules, install, success_out="success.txt", fail_out="fail.txt"):
    dic1 = {0:[], 1:[], 2:[], 3:[]}
    dic2 = {
        0: "installed",
        1: "not installed",
        2: "can't be located",
        3: "can't be checked"
    }
    dic3 = {}

    for mdl in missing_modules:
        status = check_module(mdl)
        if status==1 and install:
            print(f"Installing {mdl}")

            try:
                subprocess.run(["cpan", "-T", mdl], capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                msg = (e.stderr or e.stdout or str(e)).strip()
                dic3[mdl] = f"Unexpected error installing {mdl}: {msg}"
            
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

        if dic2.items():
            print("\nOther:")
        for status,msg in dic2.items():
            list_txt = "\n\t".join(dic1[status])
            print(f"{msg}:{list_txt}")

def txt2dic(txt):
    """
    Read a tab-delimited file into a dict {key: value}.
    Skips blank lines and lines without at least 2 columns.
    """
    try:
        dic = {}
        with open(txt, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.split("\t")
                if len(line)>=2:
                    dic[line[0]] = line[1]

    except FileNotFoundError:
        raise RuntimeError(f"File not found: {txt}")

    except PermissionError:
        raise RuntimeError(f"No permission to read: {txt}")

    except UnicodeDecodeError:
        raise RuntimeError(f"File is not valid UTF-8: {txt}")

    except OSError as e:
        raise RuntimeError(f"Unexpected OS error when opening {txt}: {e}")

    return dic

def parse_arguments():
	parser = argparse.ArgumentParser(description="Install Perl packages on the cluster")
	parser.add_argument("--vnew", help="New Perl version")
	parser.add_argument("--vold", help="Old Perl version")
	parser.add_argument("--migrate", action="store_true", help="Install all vold packages in vnew")
	parser.add_argument("--install", help="package(s) to install in vnew, divided by comma")
	args = parser.parse_args()

	v_new = args.vnew or "5.42.0"
	v_old = args.vold or "5.26.1"

	return [v_new, v_old, args.migrate, args.install]

def main():
    print(f"Python version: {sys.version_info}")
    if input("This script requires Python 3.7 or higher. Are you using the correct version? [y/N]: ").lower().strip() not in ["y", "yes"]:
        sys.exit(1)

    os.chdir("/group/rccadmin/work/mkeith/perl")
    [v_new, v_old, migrate, install] = parse_arguments()

    if migrate:
        try:
            # Put the list of modules from the new version in dictionary
            dic_new = txt2dic(f"{v_new}.txt")

            # Put the list of modules from the old version in dictionary
            dic_old = txt2dic(f"{v_old}.txt")

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
