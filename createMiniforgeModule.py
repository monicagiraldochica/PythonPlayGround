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
    print(f"Python version: {major}.{minor}.{micro}\n")
    if major==0 or minor==0 or major<3 or minor<7:
        print("This script requires Python 3.7 or higher.")
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

    input("ssh login node [Enter]")
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

        venv_python = input(f"What python version is required by {main_pkg}/{version} (i.e. python>=3.10, Enter if no specific version required): ") or f"python={default_py}"
        input(f"\nconda create -n {env_name} {venv_python} [Enter]")

    if os.path.isdir(forge_dir):
        input(f"\nconda activate {env_name} [Enter]")
    else:
        print(f"Conda dir was not created: {forge_dir}")
        sys.exit(1)

    req_files = []
    if input("\nDo you need to clone any repos? [y/N]: ").strip().lower() in ("y", "yes"):
        repos = input("https git repos divided by comma: ").split(",")
        if len(repos)>0:
            if not os.path.isdir(build_path):
                os.makedirs(build_path)

            for repo in repos:
                repo_name = repo.split("/")[-1].replace(".git", "")
                dest = f"{build_path}/{repo_name}"

                if not os.path.isdir(dest):
                    input(f"\nDownloading {repo} to {dest} [Enter]")
                    cmd = ["git", "clone", repo, dest]
                    print(" ".join(cmd))

                    [returncode, stderr, stdout] = installib.runBash(cmd)
                    if returncode!=0 or (not os.path.isdir(dest)):
                        err = (stderr or stdout or "")
                        print(f"Could not download {repo_name}: {err}")
                        sys.exit(1)

                    input(f"Successfully downloaded {repo_name} [Enter]")

                else:
                    print(f"\n{dest} already exists")

                req_file = f"{dest}/requirements.txt"
                if os.path.isfile(req_file):
                    req_files+=[req_file]

    if input("\nDo you need to run any pip installs? [y/N]").strip().lower() in ["y", "yes"]:
        which_pip = input("\nrun 'which pip' and paste here the output: ")
        if which_pip!=f"{forge_path}/pip":
            input(f"*** DO NOT PROCEED UNTIL YOU THE RESULT OF 'which pip' IS {forge_path}/pip *** [Enter]")

        print("\nAfter each pip install run 'conda list | grep <program>' to check that it was indeed installed, and run any tests.\nDo not proceed with the next dependency until the previous one is installed and tested.\nRemember to add the version of each dependency if a specific version is needed!\n")
        pips = input("List of programs to install using pip divided by comma: ").strip().split(",")
        for pip_install in pips:
            input(f"pip install {pip_install} [Enter]")
            input(f"conda list | grep {pip_install} [Enter]")
            input(f"Run a test command for {pip_install} [Enter]")

    input("\nRun any conda install commands.\nDon't do Ctrl-C after you hit proceed! That will not do a clean end and will corrupt the environment!\nCheck each conda install with 'conda list | grep <pkg>' [Enter]")

    if len(req_files)>0:
        msg = f"\nFound {len(req_files)} requirement files in the downloaded repos. Do you want to check that all the requirements are installed in the environment? [y/N]: "
        if input(msg).strip().lower() in ("y", "yes"):
            for req_file in req_files:
                with open(req_file, "r") as fin:
                    line = fin.readline()
                    input(f"conda list | grep {line} [Enter]")

    input(f"\nTest the conda environment. The list of commands for {main_pkg} can be found in {forge_path}. [Enter]")

    input(f"\nconda deactivate [Enter]")

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
        print("Module help can have new lines. Press Ctrl-D when done.\nModule help:\n")
        ml_help = sys.stdin.read().strip()
        if input(f"Does {main_pkg} has a GUI? [y/N]: ").strip().lower() in ("y", "yes"):
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
        desc = input("Description: ").strip()
        url = input("URL: ")
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

        if input("Does any variables need to be set? [y/N]: ").strip().lower() in ("yes", "y"):
            array = input("VAR:value divided by comma: ").split(",")
            if len(array)>0:
                content+="\n"
            for var_info in array:
                pair = var_info.split(":")
                if len(pair)==2:
                    content+=f'setenv("{pair[0]}", "{pair[1]}")'

        mdl_deps = input("List dependencies divided by comma: ").strip().lower().split(",")
        mdl_deps = [x for x in mdl_deps if x != ""]
        if len(mdl_deps)>0:
            content+="\n"
            for dep in mdl_deps:
                content+=f'depends_on("{dep}")'

            if any(dep.startswith("python/3") for dep in mdl_deps):
                content+="\n--set_alias(\"python\", \"python3\")"

        Path(ml_folder).mkdir(parents=True, exist_ok=True)
        with open(new_ml, "w") as f1:
            f1.write(content)

        if len(ml_avail)>0:
            print(f"\nOther available versions for this module: {', '.join(ml_avail)}")

            if input("Will this be the default and highest version? [Y/n]: ").strip().lower() in ("n", "no"):
                default = input("Default version: ").strip()
                default_lua = f"{ml_folder}/{default}.lua"
                if os.path.isfile(default_lua):
                    os.symlink(default_lua, f"{ml_folder}/default")
                    print(f"Symlink created from {default_lua} to {ml_folder}/default")

    print("\nCompare new module file with an older one that also uses conda:")
    [returncode, stderr, stdout] = installib.runBash([["bash", "-lc", "grep -r conda | tail -n 1 | cut -d: -f1"]])
    if returncode!=0:
        print(f"vi /hpc/modulefiles/{stdout}")
    input(f"vi {new_ml} [Enter]")

    # Test final module
    print(f"\nAvailable packages for {main_pkg}:")
    input(f"ml avail {main_pkg} [Enter]")
    print(f"\nModule information:")
    input(f"ml show {main_pkg}/{version} [Enter]")

    input(f"\nTest the final module. The list of commands for {main_pkg} can be found in {forge_path}. [Enter]")

if __name__ == "__main__":
    main()