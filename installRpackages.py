#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Install R packages"

import os

os.chdir("/group/rccadmin/work/mkeith/R")
v_new = "4.5.0"
v_old = "4.4.2"

# Get the list of packages in the new version
# Opening in write mode will empty it's previous content if file exist
fnew = open(v_new+".txt",'w')
for item in sorted(os.listdir("/hpc/apps/R/"+v_new+"/lib64/R/library/"), key=str.casefold):
	if not item.startswith("00LOCK"):
		_ = fnew.write(item+"\n")
fnew.close()

# Get the list of packages in the old version
fold = open(v_old+".txt",'w')
for item in sorted(os.listdir("/hpc/apps/R/"+v_old+"/lib64/R/library/"), key=str.casefold):
        if not item.startswith("00LOCK"):
                _ = fold.write(item+"\n")
fold.close()

# Get the list of missing packages
if os.path.exists("diff.txt"):
	 os.remove("diff.txt")
os.system("diff "+v_new+".txt "+v_old+".txt >> diff.txt")

# Create files to store the libraries that successfully & unsuccessfully installed
fout1 = open("sucess.txt",'w')
fout1.close()
fout2 = open("fail.txt",'w')
fout2.close()

# Install dependencies of some missing packages
dependencies = ["ggforce", "terra", "pak", "remotes"]
for dep in dependencies:
    print("Installing "+dep+" (dependency)...\n")
    print("Rscript -e \"install.packages('"+dep+"')\"")
    os.system("Rscript -e \"install.packages('"+dep+"')\"")

if not os.path.exists("/adminfs/builds/R-4.5.0/packages"):
    os.mkdir("/adminfs/builds/R-4.5.0/packages")
os.chdir("/adminfs/builds/R-4.5.0/packages")
# THIS LINK WILL NEED TO BE MODIFIED FOR NEW VERSIONS!
os.system("wget https://cran.r-project.org/src/contrib/Archive/multicross/multicross_2.1.0.tar.gz")
os.system("R CMD INSTALL multicross_2.1.0.tar.gz")
os.chdir("/scratch/g/rccadmin/mkeith/R")

# Install missing packages
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

fin = open("diff.txt","r")
for line in fin:
	line = line.replace("\n","").replace("> ","")
	if line.startswith("<") or line[0].isdigit() or line in git_pkgs.keys() or "Giotto" in line:
		continue

	fout1 = open("sucess.txt","r")
	fout2 = open("fail.txt","r")
	output1 = os.popen("cat sucess.txt | grep "+line+" | head -n 1").read().replace("\n","")
	output2 = os.popen("cat fail.txt | grep "+line+" | head -n 1").read().replace("\n","")
	fout2.close()
	fout1.close()
	if output1==line or output2==line:
		continue

	# Using the default install method
	print("Installing "+line+"...\n")
	print("Rscript -e \"install.packages('"+line+"')\"")
	os.system("Rscript -e \"install.packages('"+line+"')\"")

	if os.path.isdir("/hpc/apps/R/"+v_new+"/lib64/R/library/"+line+"/"):
		print("\nsucess\n")
		fout1 = open("sucess.txt","a")
		_ = fout1.write(line+"\n")
		fout1.close()
	else:
		# Using Bioconductor
		print("\nTrying with bioconductor...")
		print("Rscript -e \"BiocManager::install(c('"+line+"'))\"")
		os.system("Rscript -e \"BiocManager::install(c('"+line+"'))\"")
		
		if os.path.isdir("/hpc/apps/R/"+v_new+"/lib64/R/library/"+line+"/"):
			print("\nsucess\n")
			fout1 = open("sucess.txt","a")
			_ = fout1.write(line+"\n")
			fout1.close()
		else:
			print("\nfailure\n")
			fout2 = open("fail.txt","a")
			_ = fout2.write(line+"\n")
			fout2.close()
fin.close()

# Install Git packages
for pkg,repo in git_pkgs.items():
	print("\nInstalling "+pkg+"...")
	print("Rscript -e \"devtools::install_github('"+repo+"')\"")
	os.system("Rscript -e \"devtools::install_github('"+repo+"')\"")

	if os.path.isdir("/hpc/apps/R/"+v_new+"/lib64/R/library/"+line+"/"):
		print("\nsucess\n")
		fout1 = open("sucess.txt","a")
		_ = fout1.write(line+"\n")
		fout1.close()
	else:
		print("\nfailure\n")
		fout2 = open("fail.txt","a")
		_ = fout2.write(line+"\n")
		fout2.close()
	
# Install Giotto packages
print("Rscript -e \"pak::pkg_install('drieslab/Giotto')\"")
os.system("Rscript -e \"pak::pkg_install('drieslab/Giotto')\"")
