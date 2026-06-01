#!/usr/bin/env python3
__author__ = "Monica Keith"
__purpose__ = "Common functions to install modules in the cluster"

import subprocess
import sys
from pathlib import Path
import os
import re
import shutil
import textwrap

def runBash(cmd, output_file: str=""):
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

def checkPythonVers(req_major: int=0, req_minor: int=0, req_micro: int=0):
    python_info = sys.version_info
    major = python_info.major or 0
    minor = python_info.minor or 0
    micro = python_info.micro or 0
    print(f"Python version: {major}.{minor}.{micro}")

    if major<req_major or minor<req_minor or micro<req_micro:
        return False, major, minor, micro
    return True, major, minor, micro

def downloadPackage(download_in_apps: bool, pkg_url: str, mdl_name: str, mdl_vers: str, git: bool=False):
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

def version_key(s):
    return tuple(map(int, s.split('/')[1].split('.')))

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

    modules = [m for m in re.findall(r'\S+', txt) if m.startswith(f"{pkg}/")]
    return sorted(modules, key=version_key)

def contentFolder(path: str) -> str:
    path = path[:-1] if path.endswith("/") else path
    returncode, stderr, stdout = runBash(["ls", "-l", path])
    
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"ERROR: Could not get the content of {path}: {err}")
        return None
    
    return stdout

def createMdlFile(mdl_name: str, mdl_version: str, bin_path: str, conda: bool, git_paths, db_env_var: str="", db_folder: str="", known_ml_deps=[]) -> bool:
    ml_folder = f"/hpc/modulefiles/{mdl_name}"
    new_ml = f"{ml_folder}/{mdl_version}.lua"
    ml_avail = availableModules(mdl_name)
    Path(ml_folder).mkdir(parents=True, exist_ok=True)

    # Copy module file from a previous version
    if (not os.path.isfile(new_ml)) and ml_avail:
        if input(f"Other lua files exist for {mdl_name}, do you want to copy one of the previous ones instead of creating the lua from scratch? [Y/n]: ").lower().strip() not in ["n", "no"]:
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
            print("Module help can have new lines. Press Ctrl-D when done.\nModule help (leave empty if no help): ")
            ml_help = sys.stdin.read().strip()
            ml_help = ''.join(c for c in ml_help if c.isprintable())

        else:
            try:
                with open(help_file, "r") as fin:
                    ml_help = fin.read()

            except Exception as e:
                print(f"WARNING: Could not read {help_file}. Leaving help content empty: {e}")
                ml_help = ""

        if input(f"\nDoes {mdl_name} uses a GUI? [y/N]: ").strip().lower() in ("y", "yes"):
            msg="Make sure you connect using -XY flag if planning to use the GUI.\nFor Mac users: make sure you have XQuartz installed."
            if ml_help:
                ml_help+=f"\n\n"
            ml_help+=msg

        py_files = [f for f in contentFolder(bin_path).split("\n") if f.endswith(".py")]
        if py_files:
            if ml_help:
                ml_help+=f"\n\n"
            ml_help+=f"Run '{py_files[0]} -h' instead of 'python {py_files[0]} -h'"

        # Create category string
        print("\nCategory ideas: Applications, Bioinformatics, biology, genomics, imaging, neuroimaging, chemistry, statistics, devel, math, fluid dynamics, data analytics, deep learning, machine learning, system, graphics")
        categories = input("Categories: ").strip()
        categories = ''.join(c for c in categories if c.isprintable())

        # Description and URL
        desc = input("\nDescription: ").strip()
        desc = ''.join(c for c in desc if c.isprintable())
        url = input("\nURL: ").strip()
        url = ''.join(c for c in url if c.isprintable())

        # Clear conda environments
        if conda:
            init_line = 'execute{cmd="source " .. conda_dir .. "/etc/profile.d/conda.sh; conda activate " .. myModuleName() .. "-" .. myModuleVersion() .. "; export -f " .. funcs, modeA={"load"}}'
            python_line = 'family("python")'
            try:
                with open("unload_cmd.txt", "r") as fin:
                    unload_line = fin.read()
            except Exception as e:
                print(f"WARNING: lua file will be incomplete, the content ot clear environments could not be loaded: {e}")
                unload_line = ""
        else:
            init_line = python_line = unload_line = ""

        # Finalize content
        content = textwrap.dedent(f"""\
        help([[
        {ml_help}
        ]])

        whatis("Name:     "..myModuleName())
        whatis("Version:  "..myModuleVersion())
        whatis("Category: {categories}")
        whatis("Description: {desc}")
        whatis("URL: {url}")
        """)

        # Add Git Apps if applicable
        for git_dir in git_paths:
            content+=f'pretend_path("PATH", "{git_dir}")\n'

        # Add environmental variable for DB path if applicable
        if db_env_var and db_folder:
            content+=f'setenv("{db_env_var}", "{db_folder}"\n)'

        # Add conda lines if applicable
        if conda:
            content+=textwrap.dedent(f"""\
                                    
            local conda_dir = "/hpc/apps/miniforge"
            local funcs = "conda __conda_activate __conda_hashr __conda_reactivate __conda_exe"

            -- Initialize conda and activate environment
            {init_line}

            -- Unload environments and clear conda from environment
            {unload_line}

            -- Prevent from being loaded with another system python or conda environment
            {python_line}
            """)
        else:
            content+='pathJoin("/hpc/apps", myModuleName(), myModuleVersion())'
            content+='prepend_path("PATH", root_dir)'

            # Add variables to PATH
            if os.path.isdir(bin_path):
                content+='prepend_path("PATH", pathJoin(root_dir, "bin"))'
            if os.path.isdir(bin_path.replace("/bin", "/src")):
                content+='prepend_path("PATH", pathJoin(root_dir, "src"))'
            if os.path.isdir(bin_path.replace("/bin", "/include")):
                content+='prepend_path("PATH", pathJoin(root_dir, "include"))'
            if os.path.isdir(bin_path.replace("/bin", "share/man")):
                content+='prepend_path("PATH", pathJoin(root_dir, "share/man"))'
            if os.path.isdir(bin_path.replace("/bin", "/lib64")):
                content+='prepend_path("LD_LIBRARY_PATH", pathJoin(root_dir, "lib64"))'
                if os.path.isdir(bin_path.replace("/bin", "/lib64/pkgconfig")):
                    content+='prepend_path("PKG_CONFIG_PATH", pathJoin(root_dir, "lib64/pkgconfig"))'
            elif os.path.isdir(bin_path.replace("/bin", "/lib")):
                content+='prepend_path("LD_LIBRARY_PATH", pathJoin(root_dir, "lib"))'
                if os.path.isdir(bin_path.replace("/bin", "/lib/pkgconfig")):
                    content+='prepend_path("PKG_CONFIG_PATH", pathJoin(root_dir, "lib/pkgconfig"))'

        # Add any additional variables
        if input("\nDoes any variables need to be set? [y/N]: ").strip().lower() in ("yes", "y"):
            array = input("VAR:value divided by comma: ").split(",")
            if array:
                content+="\n"
            for var_info in array:
                pair = var_info.split(":")
                if len(pair)==2:
                    content+=f'setenv("{pair[0]}", "{pair[1]}")'

        # Add aliases
        if input("\nDo you want to set any aliases? [y/N]: ").strip().lower() in ("yes", "y"):
            array = input("alias:orig_func divided by comma: ").split(",")
            if array:
                content+="\n"
            for alias_info in array:
                pair = alias_info.split(":")
                if len(pair)==2:
                    content+=f'set_alias("{pair[0]}", "{pair[1]}")'

        # Add any module dependencies
        if not known_ml_deps:
            mdl_deps = input("\nList any module dependencies divided by comma: ").strip().lower().split(",")
            mdl_deps = [x for x in mdl_deps if x != ""]
        else:
            mdl_deps = input(f"\nList any module dependencies (other than {','.join(known_ml_deps)}) divided by comma: ").strip().lower().split(",")
            mdl_deps = known_ml_deps.extend(x for x in mdl_deps if x != "")
        if mdl_deps:
            content+="\n"
            for dep in mdl_deps:
                content+=f'depends_on("{dep}")'

        # Write the created content in the module file
        try:
            with open(new_ml, "w") as f1:
                f1.write(content)
        except Exception as e:
            print(f"Error: could not create module file: {e}")
            return False
        
        # Create symlink to 'latest' if this will not be the default version
        if ml_avail:
            print(f"\nOther available versions for this module: {', '.join(ml_avail)}")
            if input("Will the highest version be the default? [Y/n]: ").strip().lower() in ("n", "no"):
                default = input("Default version: ").strip()
                default_lua = f"{ml_folder}/{default}.lua"
                if os.path.isfile(default_lua):
                    os.symlink(default_lua, f"{ml_folder}/default")
                    print(f"Symlink created from {default_lua} to {ml_folder}/default")
                else:
                    print(f"WARNING: {default_lua} not found, leaving the highest version as default.")

        return True
    
def cloneRepos(mdl_name: str, mdl_version: str):
    git_dirs = []
    if input("\nDo you need to clone any repos? [y/N]: ").strip().lower() in ("y", "yes"):
        repos = input("https git repos divided by comma: ").split(",")
        for repo in repos:
            repo_name = repo.split("/")[-1].replace(".git", "")
            download_in_apps = input(f"Does {repo_name} need to be downloaded in /hpc/apps? [y/N]: ").strip().lower() in ["y", "yes"]
            download_dir = f"/hpc/apps/{mdl_name}/{mdl_version}" if download_in_apps else f"/adminfs/builds/{mdl_name}/{mdl_version}"

            # Check that the repository wasn't already downloaded, otherwise, download
            if os.path.isdir(download_dir):
                print(f"{download_dir} already exists, skipping this download.")
            else:
                returncode, stderr, stdout, download_dir = downloadPackage(download_in_apps, repo, mdl_name, mdl_version, True)
                if returncode!=0:
                    err = (stderr or stdout or "").strip()
                    print(f"ERROR: could not download {mdl_name}: {err}")
                    sys.exit(1)
                print(f"Package successfully downloaded to {download_dir}")
            git_dirs+=[download_dir]

            req_file = f"{download_dir}/requirements.txt"
            if os.path.isfile(req_file):
                if input(f"A requirements.txt file was found in {repo_name}. Do you want to install these requirements? [Y/n]: ").strip().lower() not in ["n", "not"]:
                    input(f"cd {download_dir} [Enter]")
                    input("python -m pip install -r requirements.txt [Enter]")

                    print("Check that all requirements where successfully installed:")
                    with open(req_file, "r") as fin:
                        line = fin.readline().lower
                        if line.contains(">="):
                            line = line.split(">=")[0]
                        input(f"conda list | grep {line} [Enter]")

    return git_dirs