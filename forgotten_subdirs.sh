#!/bin/bash
# Author: Monica Keith
# Created: 2025-09-26
# Description: Find the subfolders that were accessed the longest ago inside a folder

## Global variables
nlines=0
searchdir=""
outfile=""

## Functions
printhelp(){
	echo -e "Mandatory flags:\n" \
		"\t-n N\t: Print N lines max\n" \
		"\t-f folder\t: Search folder\n"
	exit
}

parse_args() {
	while getopts ":hn:o:f:" opt; do
		case $opt in
			h) printhelp;;
			n) nlines=$OPTARG;;
			o) outfile=$OPTARG;;
			f) 
				searchdir=$OPTARG
				# Remove trailing backslash if present
				if [[ "${searchdir: -1}" == '/' ]]; then
					searchdir="${searchdir::-1}"
				fi
				;;
			\?) echo "Invalid option: -$OPTARG" >&2; exit 1;;
			:) echo "Option -$OPTARG requires an argument." >&2; exit 1;;
		esac
	done
}

main() {
	parse_args "$@"

    # Checks
    if [[ -z "$searchdir" || -z "$outfile"  ]]; then
        echo "Error: -f and -o flags cannot be missing." >&2
        exit 1
    fi

    if [[ -z "$nlines" || ! "$nlines" =~ ^[1-9][0-9]*$ ]]; then
        echo "Error: -n must be a positive integer greater than zero." >&2
        exit 1
    fi

    if [[ ! -d "$searchdir" ]]; then
        echo "Error: searchdir '$searchdir' does not exist or is not a directory." >&2
        exit 1
    fi

	# Include hidden files/folders in globbing
	shopt -s dotglob

	for dir in "$searchdir"/*; do
		# Find the oldest access time among files inside the directory
		newest_access=$(find "$dir" -type f -printf '%A@ %p\n' 2>/dev/null | sort -n | head -n1 | awk '{print $1}')

		# If the directory has no files, fallback to directory's own access time
		[ -z "$newest_access" ] && newest_access=$(stat -c %X "$dir")

		# Convert access time to human-readable format
		newest_access=$(date -d @"$newest_access" '+%Y-%m-%d %H:%M:%S')
		
		echo -e "${newest_access}\t${dir}"
		(( i+=1 ))
	done | sort -k1,2 | head -n "$nlines" > "$outfile"

	# Disable dotglob to restore default behavior
	shopt -u dotglob
}

main "$@"