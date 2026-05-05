#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Production"
__purpose__ = "Common functions to install modules in the cluster"

import subprocess
from typing import Sequence

def runBash(cmd: Sequence[str], output_file:str=None):
    file_handle = None

    try:
        if output_file:
            file_handle = open(output_file, "w")
        stdout_target = file_handle if output_file else subprocess.PIPE

        # text=True: makes stdout and stderr strings instead of bytes
        # check=True: if there's an error, an exception is produced
        result = subprocess.run(cmd, stdout=stdout_target, stderr=subprocess.PIPE, text=True, check=True)
        stdout = "" if output_file else result.stdout
        return [result.returncode, result.stderr, stdout]
    
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e)).strip()
        return [e.returncode, err, ""]
    
    finally:
        if file_handle:
            file_handle.close()