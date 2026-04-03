#!/usr/bin/env python3
__author__ = "Monica Keith"

import subprocess
import sys
import argparse
import re
import os
import shutil
import textwrap

def parse_arguments():
    parser = argparse.ArgumentParser(description="Install bew nodule using miniforge")
    parser.add_argument("--main-package", help="Name of the module to be created", required=True)
    parser.add_argument("--version", help="Module version", required=True)
    args = parser.parse_args()

    return [args.main_package, args.version]

def getCondaVersion():
    try:
        result = subprocess.run(["conda","--version"], check=True, capture_output=True, text=True).stdout
        match = re.search(r"(\d+\.\d+\.\d+)", result)
        return match.group(1) if match else None
    
    except FileNotFoundError:
        return None
    
    except subprocess.CalledProcessError:
        return None

def availableModules(pkg: str):
    cmd = f"module avail {pkg}"
    result = subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")
    matches = re.findall(rf'\b{re.escape(pkg)}/[^\s]+', out)

    return matches

def contentFolder(path: str):
    path = path[:-1] if path.endswith("/") else path
    cmd = f"ls -1 {path}"
    result = subprocess.run(["bash", "-lc", cmd], check=True, capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")

    return out

def downloadedMiniforgeVersions(pkg: str, path:str):
    out = contentFolder(path)
    names = re.findall(rf'^{re.escape(pkg)}-[^/\s]+$', out, flags=re.MULTILINE)

    return [f"{path}/{name}" for name in names]

def main():
    # Check conda version
    rVers = getCondaVersion()
    if rVers is None:
        print("Miniforge NOT loaded. Run: module load miniforge")
        sys.exit(1)

    # Check python version
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    print(f"Python version: {major}.{minor}.{micro}\n")
    if major==0 or minor==0 or major<3 or minor<7:
        print("This script requires Python 3.7 or higher.")
        sys.exit(1)

    [main_package, version] = parse_arguments()

    # Paths
    build_path = f"/adminfs/builds/{main_package}/git_repos"
    ml_folder = f"/hpc/modulefiles/{main_package}"
    new_ml = f"{ml_folder}/{version}.lua"
    forge_envs = "/hpc/apps/miniforge/envs"
    forge_path = f"{forge_envs}/{env_name}/bin"
    apps_path = f"/hpc/apps/{main_package}"
    db_folder = f"/hpc/refdata/{main_package}"

    input("sudo su - [Enter]")
    input("ml load miniforge [Enter]")

    ml_avail = availableModules(main_package)
    create_env = True

    # The module is already installed
    if f"{main_package}/{version}" in ml_avail:
        print(f"\nGood news! {main_package}/{version} is already installed!")
        sys.exit(1)
    
    # A different version of the module was installed
    elif len(ml_avail)>0:
        if input(f"\nA different version of {main_package} is installed: {', '.join(ml_avail)}\nDo you want to proceed installing {main_package}/{version}? [y/N]: ").strip().lower() not in ("yes", "y"):
            sys.exit(1)
    
    else:
        downloads = downloadedMiniforgeVersions(main_package, forge_envs)

        if len(downloads)>0:
            msg = f"\nA previous miniforge environment was created for {main_package} ({', '.join(downloads)}), "

            # The miniforge environment was previously created, but not the module
            if (not os.path.isdir(ml_folder)):
                create_env = False
                msg+="but not the module.\nDo you want to proceed? [y/N]: "

            # The module was created at some point, but it was disabled
            else:
                msg+=f"and there's a module folder for this app ({ml_folder}). However, the module is not available.\nDo you want to proceed? [y/N]: "            

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

        elif os.path.isdir(apps_path):
            msg = f"{main_package} was previously downloaded in {apps_path}, outside miniforge, but no module was created.\nContent of {apps_path}:\n{contentFolder(apps_path)}\nDo you want to proceed? [y/N]: "

            if input(msg).strip().lower() not in ("yes", "y"):
                sys.exit()

    use_pip = input("\nAre you installing using pip inside this conda environment? [Y/n]: ").strip().lower() not in ("n", "not")
    env_name = f"{main_package}-{version}"
    if create_env:
        venv_python = input(f"What python version is required by {main_package}/{version} (i.e. python>=3.10, Enter if no specific version required): ")
        if (not venv_python) and use_pip:
            print("*** YOU NEED TO INSTALL PYTHON INSIDE THE CONDA ENV OR IT WILL INSTALL THE PROGRAM IN BASE ***")
            venv_python = f"python={major}.{minor}.{micro}"
        
        if (not venv_python):
            input(f"\nconda create -n {env_name} [Enter]")
        else:
            input(f"\nconda create -n {env_name} {venv_python} [Enter]")

    input(f"\nconda activate {env_name} [Enter]")

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
                    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

                    if result.returncode!=0 or (not os.path.isdir(dest)):
                        err = result.stderr or result.stdout
                        print(f"Could not download {repo_name}: {err}")
                        sys.exit(1)

                    input(f"Successfully downloaded {repo_name} [Enter]")

                else:
                    print(f"\n{dest} already exists")

                req_file = f"{dest}/requirements.txt"
                if os.path.isfile(req_file):
                    req_files+=[req_file]

    if use_pip:
        which_pip = input("\nrun 'which pip' and paste here the output: ")
        if which_pip!=f"{forge_path}/pip":
            input(f"*** DO NOT PROCEED UNTIL YOU THE RESULT OF which pip IS {forge_path}/pip *** [Enter]")

        print("\nAfter each pip install run 'conda list | grep <program>' to check that it was indeed installed, and run any tests.\nDo not proceed with the next dependency until the previous one is installed and tested.\nRemember to add the version of each dependency if a specific version is needed!\n")
        pips = input("List of programs to install using pip divided by comma: ").split(",")
        for pip_install in pips:
            input(f"pip install {pip_install} [Enter]")
            input(f"conda list | grep {pip_install} [Enter]")
            msg = f"Run a test command for {pip_install}."
            if os.path.isdir(forge_path):
                msg+=f"\nThe list of commands for {main_package} can be found in {forge_path}"
            input(f"{msg} [Enter]")

    input("\nRun any conda commands.\nDon't do Ctrl-C after you hit proceed! That will not do a clean end and will corrupt the environment! [Enter]")

    if len(req_files)>0:
        msg = f"\nFound {len(req_files)} requirement files in the downloaded repos. Do you want to check that all the requirements are installed in the environment? [y/N]: "
        if input(msg).strip().lower() in ("y", "yes"):
            for req_file in req_files:
                with open(req_file, "r") as fin:
                    line = fin.readline()
                    input(f"conda list | grep {line} [Enter]")

    if input("\nDo you need to download any databases? [y/N]: ").strip().lower() in ("yes", "y"):
        if not os.path.isdir(db_folder):
            os.mkdir(db_folder)
        input(f"Download any databases to {db_folder} [Enter]")

    # Copy module file from a previous version
    if not os.path.isfile(new_ml):
        for ml in ml_avail.reverse():
            ml_path = f"{ml_folder}/{ml}.lua"
            if os.path.isfile(ml_path):
                shutil.copy(ml_path, new_ml)
                print(f"\nCopied {ml_path} to {new_ml}")
                break

    # Create a new module file
    else:
        print(f"\nCreating {new_ml}:")

        print("Module help can have new lines. Press Ctrl-D when done.\nModule help:\n")
        ml_help = sys.stdin.read().strip()
        if input(f"Does {main_package} has a GUI? [y/N]: ").strip().lower() in ("y", "yes"):
            msg="Make sure you connect using -XY flag if planning to use the GUI.\nFor Mac users: make sure you have XQuartz installed."
            if len(ml_help)>0:
                ml_help+=f"\n\n{msg}"
            else:
                ml_help=msg
        py_files = contentFolder(forge_path).split("\n")
        py_files = [f for f in py_files if f.endswith(".py")]
        if len(py_files)>0 and len(msg)>0:
            ml_help+=f"\n\nRun '{py_files[0]} -h' instead of 'python {py_files[0]} -h'"

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
        if len(mdl_deps)>0:
            content+="\n"
            for dep in mdl_deps:
                content+=f'depends_on("{dep}")'

            if any(dep.startswith("python/3") for dep in mdl_deps):
                content+="\n--set_alias(\"python\", \"python3\")"

        if not os.path.isdir(ml_folder):
            os.mkdir(ml_folder)

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

    input(f"vi {new_ml} [Enter]")

if __name__ == "__main__":
    main()