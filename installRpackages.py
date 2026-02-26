#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install R packages"

import os
import argparse
import subprocess
from shlex import quote
from datetime import date
from pathlib import Path
import sys
import re
import pandas as pd

def parse_arguments():
	parser = argparse.ArgumentParser(description="Install R packages on the cluster")
	parser.add_argument("--working-dir", help="Directory where outputs will be saved", required=True)
	parser.add_argument("--vnew", help="New R version")
	parser.add_argument("--vold", help="Old R version")
	parser.add_argument("--git-repo", help="GitHub repository")

	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument("--migrate", action="store_true", help="Install all vold packages in vnew")
	group.add_argument("--install", help="package to install in vnew")
	group.add_argument("--update", help="package(s) to update in vnew divided by comma, or path of csv file with the following columns: Index, Package, LibPath (not used), Install_Path (not used), Built (not used), ReposVer (not used), Repository.")

	args = parser.parse_args()
	
	v_new = args.vnew or "4.5.0"
	v_old = args.vold or "4.4.2"

	working_dir = args.working_dir
	if not os.path.isdir(working_dir):
		sys.exit(f"{working_dir} doesn't exist")
	working_dir = working_dir[:-1] if working_dir.endswith("/") else working_dir
	
	return [v_new, v_old, args.migrate, args.install, args.git_repo, working_dir, args.update]

def savePackageList(r_version: str, working_dir: str):
	try:
		with open(f"{working_dir}/{r_version}.txt", 'w') as fin:
			for item in sorted(os.listdir(f"/hpc/apps/R/{r_version}/lib64/R/library/"), key=str.casefold):
				if not item.startswith("00LOCK"):
					_ = fin.write(item+"\n")

	except FileNotFoundError as e:
		raise RuntimeError(f"File not found: {e}") from e
	
	except NotADirectoryError as e:
		raise RuntimeError(f"Not a directory: {e}") from e
	
	except PermissionError as e:
		raise RuntimeError(f"Permission error: {e}") from e
	
	except OSError as e:
		raise RuntimeError(f"OS error: {e}") from e

# Save the list of packages that are in v_old but not in v_new
def comparePackages(v_new: str, v_old: str, working_dir: str):
	with open(f"{working_dir}/missing.txt", "w") as f:
		subprocess.run(["grep", "-Fvx", "-f", v_old, v_new], stdout=f)

def runRcmd(r_expr: str):
	cmd = f"Rscript -e {quote(r_expr)}"
	result = subprocess.run(["bash", "-lc", cmd])

	return [result.returncode, result.stderr, result.stdout]

# Check if a package exists and is correctly installed
def isInstalled(r_version: str, package: str) -> bool:
	dir_exists = os.path.isdir(f"/hpc/apps/R/{r_version}/lib64/R/library/{package}/")	
	r_expr = f'quit(status = if (requireNamespace("{package}", quietly=TRUE)) 0 else 1)'
	can_be_loaded = (runRcmd(r_expr)[0] == 0)

	return dir_exists and can_be_loaded

def installWithRscript(r_version: str, package: str):
	print(f"Installing {package} in R/{r_version} using Rscript...")
	r_exp = f'install.packages("{package}")'
	[returncode, stderr, stdout] = runRcmd(r_exp)

	if returncode!=0 or not isInstalled(r_version, package):
		err = (stderr or stdout).strip()
		if err:
			print(err)
			return [False, f"Installation using Rscript failed with error: {err}"]
		else:
			print(f"Installation using Rscript failed with return code {returncode} (no output captured)")
			return [False, f"Installation using Rscript failed with return code {returncode} (no output captured)"]
	
	print(f"{package} was successfully installed in R/{r_version} with Rscript")
	return [True, f"Successfully installed in R/{r_version} with Rscript"]

def installWithTarball(r_version: str, package: str):
	print(f"Installing {package} in R/{r_version} using Tarball...")
	dest = Path(f"/adminfs/builds/R-{r_version}/packages")
	dest.mkdir(parents=True, exist_ok=True)

	# Download the latest tarball
	print(f"Downloading latest source tarball for {package}")
	r_expr = f'download.packages("{package}", destdir="{dest}", repos="https://cran.r-project.org", type="source")'
	if runRcmd(r_expr)[0]!=0:
		return [False, f"Could not download latest tarball for {package} from cran.r-project.org"]

	matches = sorted(dest.glob(f"{package}_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
	if not matches:
		return [False, f"No tarball found for {package}"]
	
	tarball = matches[0]
	print(f"Downloaded {tarball} in {dest}")

	# Install tarball
	cmd = f"R CMD INSTALL {quote(str(tarball))}"
	result = subprocess.run(["bash", "-lc", cmd], capture_output=True)

	if result.returncode!=0 or not isInstalled(r_version, package):
		err = (result.stderr or result.stdout).strip()
		if err:
			print(err)
			return [False, f"Installation using tarball failed with error: {err}"]
		else:
			print(f"Installation using tarball failed with return code {result.returncode} (no output captured)")
			return [False, f"Installation tarball Rscript failed with return code {result.returncode} (no output captured)"]
	
	print(f"{package} was successfully installed in R/{r_version} with tarball")
	return [True, f"Successfully installed in R/{r_version} with tarball"]

def installFromGitHub(r_version: str, repo: str, pkg: str):
	print(f"Installing {pkg} in R/{r_version} using GitHub...")

	msg = ""
	for opt in ["remotes", "devtools"]:
		r_expr = f'{opt}::install_github("{repo}")'
		[returncode, stderr, stdout] = runRcmd(r_expr)

		if returncode==0 and isInstalled(r_version, pkg):
			print(f"{pkg} was successfully installed in R/{r_version} with GitHub ({opt})")
			return [True, f"Successfully installed in R/{r_version} with GitHub {opt}"]
		
		err = (stderr or stdout).strip()
		if err:
			",".join(msg, err)

	if msg!="":
		return [False, f"Installation using GitHub failed with error: {err}"]
	return [False, f"Installation using GitHub failed (no output captured)"]

def installGiotto(r_version: str, giotto:str):
	print(f"Installing {giotto} in R/{r_version} using Giotto...")
	r_expr = f'pak::pkg_install("{giotto}")'
	[returncode, stderr, stdout] = runRcmd(r_expr)

	if returncode!=0 or not isInstalled(r_version, giotto):
		err = (stderr or stdout).strip()
		if err:
			return [False, f"Installation using Giotto failed with error: {err}"]
		else:
			print(f"Installation using Giotto failed with return code {returncode} (no output captured)")
			return [False, f"Installation using Giotto failed with return code {returncode} (no output captured)"]
	
	print(f"{giotto} was successfully installed in R/{r_version} with Giotto")
	return [True, f"Successfully installed in R/{r_version} with Giotto"]

def installBiocManager(r_version: str, package: str):
	print(f"Installing {package} in R/{r_version} using Bioconductor...")
	r_expr = f'BiocManager::install(c("{package}"))'
	[returncode, stderr, stdout] = runRcmd(r_expr)

	if returncode!=0 or not isInstalled(r_version, package):
		err = (stderr or stdout).strip()
		if err:
			return [False, f"Installation using Bioconductor failed with error: {err}"]
		else:
			print(f"Installation using Bioconductor failed with return code {returncode} (no output captured)")
			return [False, f"Installation using Bioconductor failed with return code {returncode} (no output captured)"]
	
	print(f"{package} was successfully installed in R/{r_version} with Bioconductor")
	return [True, f"Successfully installed in R/{r_version} with Bioconductor"]

# Check if a package install had already failed
def hadFailed(package:str, working_dir:str):
	if not os.path.isfile("fail.txt"):
		return False
	
	cmd = f"grep -F {quote(package)} {working_dir}/fail.txt | head -n 1 | cut -d: -f1"
	out = subprocess.run(cmd, shell=True, check=False).stdout
	if out==None:
		return False
	
	return out.strip()==package

def installPackage(r_version, working_dir, pkg_install=None, pkg_update=None, check_pastFail=True, gitRepo=None, bioc=False):
	package = pkg_install if pkg_install else pkg_update
	if package is None:
		print("No package provided")
		return [False, ""]

	if pkg_install and isInstalled(r_version, package):
		print(f"{package} is already installed in R/{r_version}")
		return [True, ""]
	
	if check_pastFail and hadFailed(package, working_dir):
		print(f"{package} installation already failed")
		return [False, ""]
	
	if gitRepo:
		return installFromGitHub(r_version, gitRepo, package)
	
	if package.endswith("/Giotto"):
		return installGiotto(r_version, package)
	
	if (not bioc):
		[success, msg] = installWithRscript(r_version, package)
		if success:
			return [success, msg]
	
	if (not bioc):
		[success, msg2] = installWithTarball(r_version, package)
		if success:
			return [success, ", ".join(msg, msg2)]

	[success, msg3] = installBiocManager(r_version, package)
	return [success, ", ".join(msg, msg2, msg3)]

def saveInstallAttempt(success: bool, message: str):
	today = date.today().strftime("%Y_%m_%d")
	line = message.rstrip("\r\n")+"\n"
	filename = f"{'success' if success else 'failed'}_{today}.txt"
	log_path = Path(filename)
	log_path.open("a", encoding="utf-8").write(line)

def isBiocPackage(pkg_name):
	r_code = f'''
		if (!requireNamespace("BiocManager", quietly=TRUE)) {{
			cat("UNKNOWN"); quit(status=0)
		}}

		avail <- tryCatch(BiocManager::available(), error=function(e) character())
		cat(if ("{pkg_name}" %in% avail) "YES" else "NO")
	'''

	try:
		result = subprocess.run(["R", "--slave", "-e", r_code], capture_output=True, text=True, check=True)
		out = (result.stdout or "").strip()
		return out=="YES"
	
	except FileNotFoundError:
		return False
	
	except subprocess.CalledProcessError:
		return False

def migrateVersions(v_new, v_old, working_dir):
	# Get the list of packages in the new version
	savePackageList(v_new, working_dir)

	# Get the list of packages in the old version
	savePackageList(v_old, working_dir)

	# Get the list of packages missing in the new version
	comparePackages(v_new, v_old, working_dir)

	# Install known dependencies of known some missing packages
	for dep in ["ggforce", "terra", "pak", "remotes", "multicross", "drieslab/Giotto"]:
		[success, msg] = installPackage(v_new, working_dir, pkg_install=dep)
		if msg!="":
			saveInstallAttempt(success, f"{dep}: {msg}")

	# Install Git packages
	git_pkgs = {
		"SeuratData":"satijalab/seurat-data",
		"SeuratDisk":"mojaveazure/seurat-disk",
		"SeuratWrappers":"satijalab/seurat-wrappers",
		"CellChat":"jinworks/CellChat",
		"monocle3":"cole-trapnell-lab/monocle3",
		"presto":"immunogenomics/presto",
		"proteoDA":"ByrumLab/proteoDA",
		"rbokeh":"hafen/rbokeh",
		"SCENIC":"aertslab/SCENIC",
		"SCopeLoomR":"aertslab/SCopeLoomR",
		"velocyto.R":"velocyto-team/velocyto.R",
		"SCPA":"jackbibby1/SCPA"
	}
	for pkg,repo in git_pkgs.items():
		[success, msg] = installPackage(v_new, working_dir, pkg_install=pkg, gitRepo=repo)
		if msg!="":
			saveInstallAttempt(success, f"{pkg}: {msg}")

	# Install other packages
	with open(f"{working_dir}/missing.txt", "r") as fin:
		for line in fin:
			line = line.replace("\n","").replace("> ","")
			if line.startswith("<") or line[0].isdigit():
				continue

			if isBiocPackage(line):
				installPackage(v_new, working_dir, pkg_install=line, bioc=True)

			else:
				installPackage(v_new, working_dir, pkg_install=line)

# Get list of mandatory dependencies
# repo_mode can be "cran" or "bioc"
def r_mandatory_deps_recursive(package, repo_mode="bioc", cran_repo="https://cran.r-project.org"):
	if repo_mode not in ("cran", "bioc"):
		raise ValueError("repo_mode must be 'cran' or 'bioc'")
	
	if repo_mode == "cran":
		repo_setup = f'repos <- c(CRAN = "{cran_repo}")'

	else:
		repo_setup = 'repos <- BiocManager::repositories()'
		
	r_expr = f"""
		pkg <- "{package}"
		{repo_setup}
		ap <- available.packages(repos = repos)
		deps <- tools::package_dependencies(
		packages = pkg,
		db = ap,
		which = c("Depends", "Imports", "LinkingTo"), recursive = TRUE)[[pkg]]

		if (is.null(deps)) quit(status = 2)  # package not found in repo index

		deps <- unique(deps)
		deps <- deps[deps != "R"]            # drop "R (>= ...)" if present
		deps <- sort(deps)
		cat(deps, sep="\\n")
	""".strip()

	[returncode, stderr, stdout] = runRcmd(r_expr)
	if returncode==2:
		where = "CRAN" if repo_mode == "cran" else "Bioconductor/CRAN repos"
		raise ValueError(f"Package '{package}' not found in {where} metadata")
	
	if returncode!=0:
		raise RuntimeError(f"Rscript failed:\n{stderr}")
	
	if not stdout:
		return []

	return [ln for ln in stdout.splitlines() if ln.strip()]

def getRversion():
	try:
		result = subprocess.run(["R","--version"], check=True, capture_output=True, text=True).stdout
		match = re.search(r"(\d+\.\d+\.\d+)", result)
		return match.group(1) if match else None
	
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

	[v_new, v_old, migrate, pkg_install, git_repo, working_dir, pkg_update] = parse_arguments()

	# Check R version
	rVers = getRversion()
	if rVers is None:
		print(f"No R loaded. Run: module load R/{v_new}")
		sys.exit(1)
	if rVers!=v_new:
		print(f"Wrong version of R loaded ({rVers}). Need {v_new}.")
		sys.exit(1)

	if input("Are you running this on a screen process? [y/N]: ") not in ("y", "yes"):
		sys.exit("This needs to run on screen process or it might disconnect in the middle of a install")

	if migrate:
		migrateVersions(v_new, v_old, working_dir)

	if pkg_install and (not git_repo):
		installPackage(v_new, working_dir, pkg_install=pkg_install, check_pastFail=False)	
	elif pkg_install:
		installPackage(v_new, working_dir, pkg_install=pkg_install, check_pastFail=False, gitRepo=git_repo)

	if pkg_update:
		bioc_packages = []
		other_packages = []
		if pkg_update.endswith(".csv"):
			if (not os.path.isfile(pkg_update)) and os.path.isfile(f"{working_dir}/{pkg_update}"):
				pkg_update = f"{working_dir}/{pkg_update}"
			if (not os.path.isfile(pkg_update)):
				print(f"Can't find {pkg_update} nor {working_dir}/{pkg_update}")
				sys.exit(1)

			df = pd.read_csv(pkg_update, index_col=0)
			for _,line in df.iterrows():
				print(f"{line.Package},{line.Repository}")
				break

		#else:
		#isBiocPackage(pkg_name)
		#installPackage(v_new, working_dir, pkg_update=pkg_update, check_pastFail=False)

if __name__ == "__main__":
    main()
