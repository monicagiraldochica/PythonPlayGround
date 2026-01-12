#!/usr/bin/env python3.9
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install Perl packages"

import subprocess
import sys
import os

def check_module(mdl: str) -> int:
    """
    Check if a Perl module is installed.
    Returns:
    0 -> Module installed
    1 -> Module not installed
    2 -> Module can't be located
    Raises:
    RuntimeError for any other unexpected Perl errors
    """
    cmd = ['perl', f"-M{mdl}", '-e', 'print "Installed\n"']
    env = os.environ.copy()
    env['PERL_MM_USE_DEFAULT'] = '1' # non-interactive module install

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        output = result.stdout.strip()  # remove trailing newlines
        return 0 if output == "Installed" else 1

    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "Can't locate" in stderr:
            return 2 # missing module
        else:
            return 3 # any other Perl compilation/runtime error

def loop(missing_modules,install):
    fout1 = None
    fout2 = None

    try:
        fout2 = open("fail.txt", 'w' if install else 'a')
        if not install:
            fout1 = open("success.txt",'w')

        for mdl in missing_modules:
            status = check_module(mdl)
            if status == 0:
                if install:
                    print(f"{mdl} is already installed")
                else:
                    fout1.write(f"{mdl}\n")

            elif status == 1:
                if install:
                    print(f"Installing {mdl}")
                    subprocess.run(["cpan", "-T", mdl], check=True)
                else:
                    fout2.write(f"{mdl} not installed\n")

            elif status == 2:
                if install:
                    print(f"{mdl} can't be located")
                else:
                    fout2.write(f"{mdl} can't be located\n")

            elif status == 3:
                if install:
                    print(f"{mdl} can't be checked")
                else:
                    fout2.write(f"{mdl} can't be checked\n")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Unexpected error installing {mdl}: {e.stderr}") from e

    except (FileNotFoundError, PermissionError, OSError) as e:
        raise RuntimeError(f"File operation failed: {str(e)}") from e

    except Exception as e:
        raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}") from e

    finally:
        if fout2:
            fout2.close()
        if fout1:
            fout1.close()

def txt2dic(txt):
    try:
        dic = {}
        with open(txt, "r") as f:
            for line in f:
                line = line.strip().split("\t")
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

def main():
    if sys.version_info < (3, 7):
        sys.exit("This script requores Python 3.7 or higher.")

    os.chdir("/group/rccadmin/work/mkeith/perl")
    v_new = "5.42.0"
    v_old = "5.26.1"

    try:
        # Put the list of modules from the new version in dictionary
        dic_new = txt2dic(f"{v_new}.txt")

        # Put the list of modules from the old version in dictionary
        dic_old = txt2dic(f"{v_old}.txt")

        # Get the list of missing packages
        missing_keys = set(dic_old.keys()) - set(dic_new.keys())

        # Install missing modules
        loop(missing_keys,True)

        # Check install
        loop(missing_keys,False)

    except Exception as err:
        print(f"Fatal error: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
