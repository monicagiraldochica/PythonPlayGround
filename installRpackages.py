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

def parse_arguments():
	parser = argparse.ArgumentParser(description="Install R packages on the cluster")
	parser.add_argument("--vnew", help="New R version")
	parser.add_argument("--vold", help="Old R version")
	parser.add_argument("--migrate", action="store_true", help="Install all vold packages in vnew")
	parser.add_argument("--install", help="package to install in vnew")
	parser.add_argument("--git-repo", help="GitHub repository")
	args = parser.parse_args()

	v_new = args.vnew or "4.5.0"
	v_old = args.vold or "4.4.2"

	return [v_new, v_old, args.migrate, args.install, args.git_repo]

def savePackageList(r_version: str):
	fin = open(f"{r_version}.txt", 'w')

	for item in sorted(os.listdir(f"/hpc/apps/R/{r_version}/lib64/R/library/"), key=str.casefold):
		if not item.startswith("00LOCK"):
			_ = fin.write(item+"\n")

	fin.close()

# Save the list of packages that are in v_old but not in v_new
def comparePackages(v_new: str, v_old: str):
	with open("missing.txt", "w") as f:
		subprocess.run(["grep", "-Fvx", "-f", v_old, v_new], stdout=f)

def runRcmd(r_version:str, r_expr: str):
	module_cmd = f"module load R/{quote(r_version)}"
	cmd = f"{module_cmd} && Rscript -e {quote(r_expr)}"
	result = subprocess.run(["bash", "-lc", cmd])

	return [result.returncode, result.stderr, result.stdout]

# Check if a package exists and is correctly installed
def isInstalled(r_version: str, package: str) -> bool:
	dir_exists = os.path.isdir(f"/hpc/apps/R/{r_version}/lib64/R/library/{package}/")	
	r_expr = f'quit(status = if (requireNamespace("{package}", quietly=TRUE)) 0 else 1)'
	can_be_loaded = (runRcmd(r_version, r_expr)[0] == 0)

	return dir_exists and can_be_loaded

def installWithRscript(r_version: str, package: str):
	print(f"Installing {package} in R/{r_version} using Rscript...")
	r_exp = f'install.packages("{package}")'
	[returncode, stderr, stdout] = runRcmd(r_version, r_exp)

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
	if runRcmd(r_version, r_expr)[0]!=0:
		return [False, f"Could not download latest tarball for {package} from cran.r-project.org"]

	matches = sorted(dest.glob(f"{package}_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
	if not matches:
		return [False, f"No tarball found for {package}"]
	
	tarball = matches[0]
	print(f"Downloaded {tarball} in {dest}")

	# Install tarball
	cmd = f"module load {quote(r_version)} && R CMD INSTALL {quote(str(tarball))}"
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
		[returncode, stderr, stdout] = runRcmd(r_version, r_expr)

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
	[returncode, stderr, stdout] = runRcmd(r_version, r_expr)

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
	[returncode, stderr, stdout] = runRcmd(r_version, r_expr)

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
def hadFailed(package):
	if not os.path.isfile("fail.txt"):
		return False
	
	cmd = f"grep -F {quote(package)} fail.txt | head -n 1 | cut -d: -f1"
	out = subprocess.run(cmd, shell=True, check=False).stdout
	if out==None:
		return False
	return out.strip()==package

def installPackage(r_version: str, package: str, check_pastFail=True, gitRepo=None):
	if isInstalled(r_version, package):
		print(f"{package} is already installed in R/{r_version}")
		return [True, ""]
	
	if check_pastFail and hadFailed(package):
		print(f"{package} installation already failed")
		return [False, ""]
	
	if gitRepo:
		return installFromGitHub(r_version, gitRepo, package)
	
	if package.endswith("/Giotto"):
		return installGiotto(r_version, package)
	
	[success, msg] = installWithRscript(r_version, package)
	if success:
		return [success, msg]
	
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

def migrateVersions(v_new, v_old):
	# Get the list of packages in the new version
	savePackageList(v_new)

	# Get the list of packages in the old version
	savePackageList(v_old)

	# Get the list of packages missing in the new version
	comparePackages(v_new, v_old)

	# Install known dependencies of known some missing packages
	for dep in ["ggforce", "terra", "pak", "remotes", "multicross", "drieslab/Giotto"]:
		[success, msg] = installPackage(v_new, dep)
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
		[success, msg] = installPackage(v_new, pkg, gitRepo=repo)
		if msg!="":
			saveInstallAttempt(success, f"{pkg}: {msg}")

	# Install normal packages
	with open("missing.txt", "r") as fin:
		for line in fin:
			line = line.replace("\n","").replace("> ","")
			if line.startswith("<") or line[0].isdigit():
				continue

			installPackage(v_new, line)

def main():
	os.chdir("/group/rccadmin/work/mkeith/R")
	[v_new, v_old, migrate, pkg_install, git_repo] = parse_arguments()

	if migrate:
		migrateVersions(v_new, v_old)

	if pkg_install:
		if not git_repo:
			installPackage(v_new, pkg_install, check_pastFail=False)
		
		else:
			installPackage(v_new, pkg_install, check_pastFail=False, gitRepo=git_repo)

if __name__ == "__main__":
    main()
