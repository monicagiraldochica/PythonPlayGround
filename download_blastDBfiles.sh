#!/bin/bash

check() {
	n=$1
	db=$2
	exist=true
	[ "$db" == "nr" ] && array=("phd" "phi" "phr" "pin" "pog" "ppd" "ppi" "psq" "pxm") || array=("nin" "nhr" "nsq" "nni" "nnd" "nhi" "nhd" "nog" "nxm")

	for ext in ${array[@]}
	do
		[ ! -f $db.$n.$ext ] && echo "missing ${db}.${n}.${ext}" && exist=false && break
 	done
 	$exist
}

download(){
	n=$1
	db=$2

	echo "## Downloading nr ${n}..."
	wget https://ftp.ncbi.nlm.nih.gov/blast/db/$db.$n.tar.gz
	echo "untaring..."
	tar -xvzf $db.$n.tar.gz
	echo "done"
}

for db in "nr" "nt"
do
	[ "$db" == "nr" ] && max=118 || max=252

	for ((i=0; i<=$max; i+=1))
	do
		if [ "${i}" -gt "99" ]
		then
			n="${i}"
		elif [ "${i}" -gt "9" ]
		then
			n="0${i}"
		else
			n="00${i}"
		fi

		check $n $db || download $n $db
		if check $n $db
		then
			echo "Successfully downloaded ${n} from ${db}"
			rm -f $db.$n.tar.gz
		else
			echo "Error downloading ${n} from ${db}"
			cont=false
			break
		fi
	done

	$cont || break
done
