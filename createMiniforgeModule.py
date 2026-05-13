#!/usr/bin/env python3
__author__ = "Monica Keith"

import sys
import argparse
import re
import os
import shutil
import textwrap
import installib
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install bew nodule using miniforge")
    parser.add_argument("--main-pkg", help="Name of the module to be created", required=True)
    parser.add_argument("--version", help="Module version", required=True)
    args = parser.parse_args()

    return [args.main_pkg, args.version]

def getCondaVersion():
    [returncode, stderr, stdout] = installib.runBash(["conda", "--version"])

    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Could not check conda version: {err}")
        return None
    
    match = re.search(r"(\d+\.\d+\.\d+)", stdout)
    return match.group(1) if match else None

def availableModules(pkg: str):
    lmod_cmd = os.environ.get("LMOD_CMD")
    if not lmod_cmd:
        print("LMOD_CMD is not set; Lmod is not initialized")
        return []
    
    [returncode, stderr, stdout] = installib.runBash([lmod_cmd, "shell", "avail", pkg])    
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Could not check available modules for {pkg}: {err}")
        return []

    matches = re.findall(rf'\b{re.escape(pkg)}/[^\s]+', stdout)
    return matches

def contentFolder(path: str):
    path = path[:-1] if path.endswith("/") else path
    [returncode, stderr, stdout] = installib.runBash(["ls", "-l", path])
    
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"Could not get the content of {path}: {err}")
        return None
    
    return stdout

def downloadedMiniforgeVersions(pkg: str, path:str):
    out = contentFolder(path)
    if out is None:
        return []
    
    names = re.findall(rf'^{re.escape(pkg)}-[^/\s]+$', out, flags=re.MULTILINE)
    return [f"{path}/{name}" for name in names]

def main():
    # Check python version
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    print(f"Python version: {major}.{minor}.{micro}")
    if major==0 or minor==0 or major<3 or minor<7:
        print("This script requires Python 3.7 or higher\n")
        sys.exit(1)

    [main_pkg, version] = parse_arguments()

    # Paths
    build_path = f"/adminfs/builds/{main_pkg}/git_repos"
    ml_folder = f"/hpc/modulefiles/{main_pkg}"
    new_ml = f"{ml_folder}/{version}.lua"
    forge_envs = "/hpc/apps/miniforge/envs"
    env_name = f"{main_pkg}-{version}"
    forge_dir = f"{forge_envs}/{env_name}"
    forge_path = f"{forge_dir}/bin"
    apps_path = f"/hpc/apps/{main_pkg}"
    db_folder = f"/hpc/refdata/{main_pkg}"

    input("\nssh into login node [Enter]")
    input("sudo su - [Enter]")
    input("ml load miniforge [Enter]")

    ml_avail = availableModules(main_pkg)
    create_env = True

    # The module is already installed
    if f"{main_pkg}/{version}" in ml_avail:
        print(f"\nGood news! {main_pkg}/{version} is already installed!")
        sys.exit(1)
    
    # A different version of the module was installed
    elif len(ml_avail)>0:
        if input(f"\nA different version of {main_pkg} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {main_pkg}/{version}? [y/N]: ").strip().lower() not in ("yes", "y"):
            sys.exit(1)
    
    else:
        downloads = downloadedMiniforgeVersions(main_pkg, forge_envs)

        if len(downloads)>0:
            msg = f"\nA previous miniforge environment was created for {main_pkg} ({', '.join(downloads)}), "

            # The miniforge environment was previously created, but not the module
            if (not os.path.isdir(ml_folder)):
                create_env = False
                msg+="but not the module.\nDo you want to proceed? [y/N]: "

            # The module was created at some point, but it was disabled
            else:
                msg+=f"and there's a module folder for this app ({ml_folder}). However, the module is not available.\nDo you want to proceed? [y/N]: "            

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit(1)

        elif os.path.isdir(apps_path):
            msg = f"{main_pkg} was previously downloaded in {apps_path}, outside miniforge, but no module was created.\nContent of {apps_path}:\n{contentFolder(apps_path)}\nDo you want to proceed? [y/N]: "

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit(1)

    if create_env:
        if micro:
            default_py = f"{major}.{minor}.{micro}"
        else:
            default_py = f"{major}.{minor}"

        venv_python = input(f"\nWhat python version is required by {main_pkg}/{version} (i.e. python>=3.10, python=3.13. [Enter] if no specific version required): ") or f"python={default_py}"
        if (not venv_python.startswith("python=")) and (not venv_python.startswith("python>")):
            venv_python = f"python={venv_python}"
        input(f"\nconda create -n {env_name} {venv_python} [Enter]")
        input(f"conda env list | grep {env_name} [Enter]")

    if os.path.isdir(forge_dir):
        input(f"\nconda activate {env_name} [Enter]")
    else:
        print(f"Conda dir was not created: {forge_dir}")
        sys.exit(1)

    if input("\nDo you need to clone any repos? [y/N]: ").strip().lower() in ("y", "yes"):
        repos = input("https git repos divided by comma: ").split(",")
        if len(repos)>0:
            for repo in repos:
                repo_name = repo.split("/")[-1].replace(".git", "")
                if input(f"Does {repo_name} need to be downloaded in /hpc/apps? [y/N]: ").strip().lower() in ["y", "yes"]:
                    dest = f"{apps_path}/{version}"
                else:
                    Path(build_path).mkdir(parents=True, exist_ok=True)
                    dest = f"{build_path}/{repo_name}"

                if not os.path.isdir(dest):
                    input(f"\nDownloading {repo} to {dest} [Enter]")
                    cmd = ["git", "clone", repo, dest]
                    print(" ".join(cmd))

                    [returncode, stderr, stdout] = installib.runBash(cmd)
                    if returncode!=0 or (not os.path.isdir(dest)):
                        err = (stderr or stdout or "")

                        if err.contains("remote: Not Found"):
                            repo = (f"The repository was not found, try one more time. git repo url: ")
                            [returncode, stderr, stdout] = installib.runBash(["git", "clone", repo, dest])
                            if returncode!=0 or (not os.path.isdir(dest)):
                                 err = (stderr or stdout or "")

                    if returncode!=0 or (not os.path.isdir(dest)):
                        print(f"Could not download {repo_name}: {err}")
                        sys.exit(1)

                    input(f"Successfully downloaded {repo_name} [Enter]")

                else:
                    print(f"\n{dest} already exists")

                req_file = f"{dest}/requirements.txt"
                if os.path.isfile(req_file):
                    if input(f"A requirements.txt file was found in {repo_name}. Do you want to install? [Y/n]: ").strip().lower() not in ["n", "not"]:
                        input(f"cd {dest} [Enter]")
                        input("python -m pip install -r requirements.txt [Enter]")

                        print("Check that all requirements where successfully installed:")
                        with open(req_file, "r") as fin:
                            line = fin.readline().lower
                            if line.contains(">="):
                                line = line.split(">=")[0]
                            input(f"conda list | grep {line} [Enter]")

    if input("\nDo you need to run any pip installs? [y/N]: ").strip().lower() in ["y", "yes"]:
        which_pip = input("\nrun 'which pip' and paste here the output: ")
        if which_pip!=f"{forge_path}/pip":
            input(f"*** DO NOT PROCEED UNTIL YOU THE RESULT OF 'which pip' IS {forge_path}/pip *** [Enter]")

        print("\nAfter each pip install run 'conda list | grep <program>' to check that it was indeed installed, and run any tests.\nDo not proceed with the next dependency until the previous one is installed and tested.\nRemember to add the version of each dependency if a specific version is needed!\n")
        pips = input("List of programs to install using pip divided by comma: ").strip().split(",")
        for pip_install in pips:
            input(f"pip install {pip_install} [Enter]")
            input(f"conda list | grep {pip_install} [Enter]")
            input(f"Run a test command for {pip_install} [Enter]")

    if input("\nDo you need to run any 'conda install' commands? [y/N]: ").strip().lower() in ["y", "yes"]:
        print("Don't do Ctrl-C after you hit proceed! That will not do a clean end and will corrupt the environment!")
        print("Check each conda install with 'conda list | grep <pkg>'")
        input(f"i.e. conda list | grep {main_pkg} [Enter]")

    # If I need to install a kernel for jupyter
    #conda install ipykernel
    # Create kernel from one of the others: /hpc/apps/miniforge/share/jupyter/kernels

    # Run tests with the conda environment activated
    print("\nTest the conda environment:")

    msg = f"The list of commands for {main_pkg} can be found in {forge_path}."
    if os.path.isdir(f"{apps_path}/{version}/bin"):
        msg+=f" And in {apps_path}/{version}/bin."
    input(f"{msg}. [Enter]")

    tests = input(f"Input file with the list of tests that you would like to run ([Enter] if no specific tests): ").strip()
    if os.path.isfile(tests):
        with open(tests, "r") as fin:
            line = fin.readline()
            input(f"{line} [Enter]")

    input(f"\nconda deactivate [Enter]")

    # Download databases
    if input("\nDo you need to download any databases? [y/N]: ").strip().lower() in ("yes", "y"):
        Path(db_folder).mkdir(parents=True, exist_ok=True)
        input(f"Download any databases to {db_folder} [Enter]")

    # Copy module file from a previous version
    if (not os.path.isfile(new_ml)) and (ml_avail is not None) and len(ml_avail)>0:
        for ml in ml_avail.reverse():
            ml_path = f"{ml_folder}/{ml}.lua"
            if os.path.isfile(ml_path):
                shutil.copy(ml_path, new_ml)
                print(f"\nCopied {ml_path} to {new_ml}")
                break

    # Create a new module file
    else:
        print(f"\nCreating {new_ml}:")

        # Create module help content
        help_file = input("\nPath to txt file with the content of the module help ([Enter] if you want to input the help manually or include no help text): ").strip()
        if not os.path.isfile(help_file):
            print("Module help can have new lines. Press Ctrl-D when done.\nModule help (leave empty if no help):")
            ml_help = sys.stdin.read().strip()
            ml_help = ''.join(c for c in ml_help if c.isprintable())
        else:
            with open(help_file, "r") as fin:
                ml_help = fin.read()

        if input(f"\nDoes {main_pkg} has a GUI? [y/N]: ").strip().lower() in ("y", "yes"):
            msg="Make sure you connect using -XY flag if planning to use the GUI.\nFor Mac users: make sure you have XQuartz installed."
            if len(ml_help)>0:
                ml_help+=f"\n\n{msg}"
            else:
                ml_help=msg
        py_files = contentFolder(forge_path).split("\n")
        py_files = [f for f in py_files if f.endswith(".py")]
        if len(py_files)>0 and len(msg)>0:
            ml_help+=f"\n\nRun '{py_files[0]} -h' instead of 'python {py_files[0]} -h'"

        # Create category string
        print("\nCategory ideas: Applications, Bioinformatics, biology, genomics, imaging, neuroimaging, chemistry, statistics, devel, math, fluid dynamics, data analytics, deep learning, machine learning, system, graphics")
        categories = input("Categories: ").strip()
        categories = ''.join(c for c in categories if c.isprintable())

        # Description and URL
        desc = input("\nDescription: ").strip()
        desc = ''.join(c for c in desc if c.isprintable())
        url = input("\nURL: ").strip()
        url = ''.join(c for c in url if c.isprintable())

        init_line = 'execute{cmd="source " .. conda_dir .. "/etc/profile.d/conda.sh; conda activate " .. myModuleName() .. "-" .. myModuleVersion() .. "; export -f " .. funcs, modeA={"load"}}'
        python_line = 'family("python")'

        if not os.path.isfile("unload_cmd.txt"):
            print("*** lua file will be incomplete, the content that goes under -- Unload environments and clear conda from environment could not be loaded ***")
            unload_line = ""
        else:
            with open("unload_cmd.txt", "r") as fin:
                unload_line = fin.read()

        content = textwrap.dedent(f"""\
        help([[
        {ml_help}
        ]])

        whatis("Name:     "..myModuleName())
        whatis("Version:  "..myModuleVersion())
        whatis("Category: {categories}")
        whatis("Description: {desc}")
        whatis("URL: {url}")

        local conda_dir = "/hpc/apps/miniforge"
        local funcs = "conda __conda_activate __conda_hashr __conda_reactivate __conda_exe"

        -- Initialize conda and activate environment
        {init_line}

        -- Unload environments and clear conda from environment
        {unload_line}

        -- Prevent from being loaded with another system python or conda environment
        {python_line}
        """)

        if input("\nDoes any variables need to be set? [y/N]: ").strip().lower() in ("yes", "y"):
            array = input("VAR:value divided by comma: ").split(",")
            if len(array)>0:
                content+="\n"
            for var_info in array:
                pair = var_info.split(":")
                if len(pair)==2:
                    content+=f'setenv("{pair[0]}", "{pair[1]}")'

        mdl_deps = input("\nList dependencies divided by comma: ").strip().lower().split(",")
        mdl_deps = [x for x in mdl_deps if x != ""]
        if len(mdl_deps)>0:
            content+="\n"
            for dep in mdl_deps:
                content+=f'depends_on("{dep}")'

            if any(dep.startswith("python/3") for dep in mdl_deps):
                content+="\n--set_alias(\"python\", \"python3\")"

        # Write the created content in the module file
        Path(ml_folder).mkdir(parents=True, exist_ok=True)
        with open(new_ml, "w") as f1:
            f1.write(content)

        # Create symlink to 'latest' if this will not be the default version
        if len(ml_avail)>0:
            print(f"\nOther available versions for this module: {', '.join(ml_avail)}")

            if input("Will this be the default and highest version? [Y/n]: ").strip().lower() in ("n", "no"):
                default = input("Default version: ").strip()
                default_lua = f"{ml_folder}/{default}.lua"
                if os.path.isfile(default_lua):
                    os.symlink(default_lua, f"{ml_folder}/default")
                    print(f"Symlink created from {default_lua} to {ml_folder}/default")

    # Check module file
    print("\nCompare new module file with another one that also uses conda:")
    [returncode, stderr, stdout] = installib.runBash(["bash", "-lc", "grep -r conda /hpc/modulefiles | tail -n 1 | cut -d: -f1"])
    if returncode!=0:
        print(f"vi /hpc/modulefiles/{stdout}")
    input(f"vi {new_ml} [Enter]")

    # Test final module
    print(f"\nAvailable packages for {main_pkg}:")
    input(f"ml avail {main_pkg} [Enter]")
    print(f"\nModule information:")
    input(f"ml show {main_pkg}/{version} [Enter]")

    # Run final tests
    print("\nTest the final module:")
    input(f"The list of commands for {main_pkg} can be found in {forge_path}. [Enter]")
    if os.path.isfile(tests):
        with open(tests, "r") as fin:
            line = fin.readline()
            input(f"{line} [Enter]")

if __name__ == "__main__":
    main()