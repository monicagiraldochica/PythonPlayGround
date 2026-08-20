#!/usr/bin/env python3
__author__ = "Monica Keith"
__status__ = "Development"
__purpose__ = "Troubleshoot cluster jobs"

# Check python version
import installib
import sys
if not installib.checkPythonVers(3, 12, 10, True)[0]:
    print("ERROR: This script requires Python 3.12.10\n")
    sys.exit(1)

import subprocess
import pandas as pd
import re
import os
import argparse
import getpass
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt

SACCT_FIELDS = [ "User", "JobName", "State", "ExitCode", "DerivedExitCode", "Partition", "WorkDir", "StdErr", "StdOut", "Submit", "Start", "End", "Elapsed", "Timelimit", "TotalCPU", "AllocCPUS", "NodeList", "ReqCPUS", "ReqMem", "MaxRSS" ]
SCONTROL_FIELDS = [ "UserId", "JobState", "Partition", "WorkDir", "StdErr", "StdOut", "Command", "RunTime", "TimeLimit", "SubmitTime", "StartTime", "EndTime", "NodeList", "ReqTRES", "AllocTRES" ]

# Only works for running, queued or recently finished jobs
def get_jobInfo_scontrol(job_id: str):
    # Run scontrol command
    cmd = ["scontrol", "show", "job", str(job_id)]
    print(f"Getting job information from: {' '.join(cmd)}")
    [returncode, stderr, stdout] = installib.runBash(cmd)
    if returncode!=0:
        err = (stderr or stdout or "").strip()
        print(f"scontrol failed: {err}")
        return pd.DataFrame()

    output = stdout.strip() if stdout else ""
    if (not output) or ("JobId" not in output):
        # Job not in memory or invalid
        return pd.DataFrame()

    # Flatten multiline scontrol output
    output = re.sub(r'\s+', ' ', output)

    # Parse key=value pairs
    data = dict(re.findall(r'(\S+?)=(\S+)', output))

    # Extract only requested fields
    info = [(field, data.get(field, "")) for field in SCONTROL_FIELDS]

    # Edit DF
    df = pd.DataFrame(info, columns=["Field", "Value"])
    df = df[~df["Value"].isin([None, '', "(null)", "None"])]
    for col in ["ReqTRES", "AllocTRES"]:
        df.loc[df["Field"]==col, "Value"] = df.loc[df["Field"]==col, "Value"].str.replace(r',billing=.*$', '', regex=True)
    df.loc[df["Field"]=="UserId", "Value"] = df.loc[df["Field"]=="UserId", "Value"].str.replace(r'\(.*$', '', regex=True)

    df = df.reset_index(drop=True)
    return df

def parseMem(value: str):
    unit = value[-1].upper()
    value = value[:-1]
    return value, unit

def editMemUsage(ReqMem: str, MaxMem: str) -> str:
    # Define unit multipliers
    units = {"K": 1024, "M": 1024**2, "G":1024**3, "T": 1024**4, "P": 1024**5}

    try:
        # Parse both inputs
        ReqVal, ReqUnit = parseMem(ReqMem)
        MaxVal, MaxUnit = parseMem(MaxMem)
        
        # Convert both values to bytes
        ReqBytes = float(ReqVal) * units[ReqUnit]
        MaxBytes = float(MaxVal) * units[MaxUnit]

        # Compute percentage
        pct = (MaxBytes / ReqBytes) * 100
        pct_str = f"{pct:.2f}".strip('0').rstrip('.')
        if not pct_str:
            pct_str = "0"

        return f"{MaxMem} ({pct_str}% of ReqMem)"
    
    except Exception:
        return MaxMem

def parseTime(t: str) -> int:
    t = t.strip()
    if "-" in t:
        days, time_part = t.split("-")
    else:
        days = 0
        time_part = t
    
    #hours, minutes, seconds = 
    time_part = time_part.split(":")
    if len(time_part)==3:
        hours = time_part[0]
        minutes = time_part[1]
        seconds = time_part[2]
    
    elif len(time_part)==2:
        hours = 0
        minutes = time_part[0]
        seconds = time_part[1].split(".")[0]

    elif len(time_part)==1:
        hours = 0
        minutes = 0
        seconds = time_part[0].split(".")[0]

    else:
        print(f"ERROR: Wrong time format: {t}")
        return -1

    return int(days)*86400 + int(hours)*3600 + int(minutes)*60 + int(seconds)

def editRunTime(walltime: str, runtime: str) -> str:
    try:
        walltime_sec = parseTime(walltime)
        runtime_sec = parseTime(runtime)
        pct = (runtime_sec/walltime_sec) * 100
        pct_str = f"{pct:.2f}".rstrip('0').rstrip('.')

        return f"{runtime} ({pct_str}% of WallTime)"
    
    except Exception:
        return runtime

def uniqueTitles(titles_orig):
    new_titles = []
    counts = {}

    for title in titles_orig:
        counts[title] = counts.get(title, 0)+1
        new_titles.append(title+"+"*(counts[title]-1))
    
    return new_titles

# Better to use for failed or completed jobs
def get_jobInfo_sacct(job_id: str, netID: str=""):
    format_str = ",".join(SACCT_FIELDS)

    try:
        # Run acct command
        cmd = ["sacct", "-j", str(job_id), f"--format={format_str}", "--units=G" , "--noheader", "--parsable2"]
        print(f"Getting job infformation from: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    except subprocess.CalledProcessError:
        # Job not found or command failed
        return pd.DataFrame()
    
    output = result.stdout.strip().splitlines()
    if len(output)<3:
        return pd.DataFrame()
    
    first_line = output[0].split("|")
    if "/" in first_line[1]:
        first_line[1] = f"OOD_{os.path.basename(first_line[1])}"
    second_line = output[1].split("|")
    third_line = output[2].split("|")

    titles = uniqueTitles([first_line[1], second_line[1], third_line[1]])
    if len(first_line)<len(SACCT_FIELDS) or len(second_line)<len(SACCT_FIELDS) or len(third_line)<len(SACCT_FIELDS):
        return pd.DataFrame()
    
    df = pd.DataFrame({ "Field": SACCT_FIELDS, titles[0]: first_line, titles[1]: second_line, titles[2]: third_line })

    # Remove JobName line since it's already titles[0]
    df = df[df["Field"]!="JobName"]

    # Edit Fields to match scontrol df
    df["Field"] = df["Field"].replace({"Submit": "SubmitTime", "End": "EndTime", "Elapsed": "RunTime", "Start": "StartTime", "User": "UserId", "State": "JobState"})
    
    # Merge Req resources lines into one
    new_vals = []
    for i in range(len(titles)):
        cpus = df.query("Field=='ReqCPUS'")[titles[i]].iloc[0]
        mem = df.query("Field=='ReqMem'")[titles[i]].iloc[0]
        nodes = len(df.query("Field=='NodeList'")[titles[i]].iloc[0].split(","))
        if cpus and mem and nodes:
            new_vals+=[f"cpu={cpus},mem={mem},node={nodes}"]
        else:
            new_vals+=[""]
    new_row = { "Field": "ReqTRES", titles[0]:new_vals[0], titles[1]:new_vals[1], titles[2]:new_vals[2] }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df = df[~df['Field'].isin(["ReqMem", "ReqCPUS"])]

    # Create new line with the CPU usage
    # CPU Utilization % = TotalCPU / (AllocCPUS × Elapsed)
    CPUtime = df.loc[df["Field"] == "TotalCPU", titles[0]].iloc[0]
    CPUtime_sec = parseTime(CPUtime)
    RunTime = df.loc[df["Field"] == "RunTime", titles[0]].iloc[0]
    RunTime = RunTime.split(" ")[0]
    RunTime_sec = parseTime(RunTime)
    AllocCPUS = int(df.loc[df["Field"] == "AllocCPUS", titles[0]].iloc[0])
    if RunTime_sec!=0:
        CPUpct = (CPUtime_sec / (AllocCPUS * RunTime_sec)) * 100
    else:
        CPUpct = 0
    new_row = {col: "" for col in df.columns}
    new_row["Field"] = "CPUpct"
    new_row[titles[0]] = CPUpct
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Remove the T from the dates
    job_cols = df.columns.drop('Field')
    fields_to_fix = [ "SubmitTime", "StartTime", "EndTime" ]
    df.loc[df['Field'].isin(fields_to_fix), job_cols] = df.loc[df['Field'].isin(fields_to_fix), job_cols].apply(lambda col: col.str.replace("T", " "))

    # Add comment to exit codes
    fields_to_fix = [ "ExitCode", "DerivedExitCode" ]
    dic_exitCodes = {
        "0:0": "Success",
        "1:0": "Application error",
        "0:15": "User cancelled job",
        "0:9": "Time limit reached, forced kill, OOM, admin kill",
        "137:0": "Job killed by SIGKILL - could be OOM or timeout",
        "0:271": "Node failure",
        "2:0": "CLI or arg parsing error in script"
    }
    for code,desc in dic_exitCodes.items():
        df.loc[df['Field'].isin(fields_to_fix), job_cols] = df.loc[df['Field'].isin(fields_to_fix), job_cols].apply(lambda col: col.str.replace(code, f"{code} ({desc})"))

    # Update StdOut
    StdOut = df.loc[df["Field"] == "StdOut", titles[0]].iloc[0]
    if isinstance(StdOut, str) and StdOut.strip():
        new_out = StdOut.replace("%x", titles[0]).replace("%j", job_id)
        if netID:
            new_out = new_out.replace("%u", netID)
        df.loc[df["Field"] == "StdOut", titles[0]] = new_out

    # Update StdErr
    StdErr = df.loc[df["Field"] == "StdErr", titles[0]].iloc[0]
    if isinstance(StdErr, str) and StdErr.strip():
        new_err = StdErr.replace("%x", titles[0]).replace("%j", job_id)
        if netID:
            new_err = new_err.replace("%u", netID)
        df.loc[df["Field"] == "StdErr", titles[0]] = new_err

    # Update MaxRSS
    ReqTRES = df.loc[df["Field"] == "ReqTRES", titles[0]].iloc[0]
    maxrss_row = df.loc[df["Field"] == "MaxRSS"].iloc[0]
    MaxRSS = next((v for v in maxrss_row.drop("Field") if pd.notna(v) and str(v).strip() != ""), "")
    # .strip in this case will be checking it he string has any non white characters
    if isinstance(ReqTRES, str) and isinstance(MaxRSS, str) and ReqTRES.strip() and MaxRSS.strip():
        ReqMem = ReqTRES.split(",")[1].replace("mem=", "")
        MaxRSS = editMemUsage(ReqMem, MaxRSS)
        df.loc[df["Field"] == "MaxRSS", titles[0]] = MaxRSS

    # Update RunTime
    RunTime = df.loc[df["Field"] == "RunTime", titles[0]].iloc[0]
    TimeLimit = df.loc[df["Field"] == "Timelimit", titles[0]].iloc[0]
    if isinstance(RunTime, str) and isinstance(TimeLimit, str) and RunTime.strip() and TimeLimit.strip():
        RunTime = editRunTime(TimeLimit, RunTime)
        df.loc[df["Field"] == "RunTime", titles[0]] = RunTime

    df = df.reset_index(drop=True)
    return df

def parse_arguments():
    parser = argparse.ArgumentParser(description="Troubleshoot a job")
    parser.add_argument("--user", help="netID", required=True)
    parser.add_argument("--outdir", help="Output folder to save any generated files", required=True)

    parser.add_argument("--stopped", action="store_true", help="Job finished running or failed")
    parser.add_argument("--queued", action="store_true", help="Job never ran")

    parser.add_argument("--jobid", help="jobID")
    parser.add_argument("--submit-date", help="Date when job was submitted (YYYY-MM-DD)")

    args = parser.parse_args()

    outdir = args.outdir
    outdir = outdir[:-1] if outdir.endswith("/") else outdir

    if args.stopped and args.queued:
        parser.error("You can't provide both --stopped and --queued flags.")

    if not (args.jobid or args.submit_date):
        parser.error("You must provide --jobid and/or --submit-date")
    if args.submit_date:
        try:
            datetime.strptime(args.submit_date, "%Y-%m-%d")
        except ValueError:
            parser.error("submit-date must be in format YYYY-MM-DD")

    return args.jobid, args.user, args.submit_date, args.stopped, args.queued, outdir

def getJobsID(submit_date: str, *, user: str="", partition: str="", start_time: str="00:00:00", end_time: str="23:59:59"):
    start = f"{submit_date}T{start_time}"
    end = f"{submit_date}T{end_time}"

    # -X: exclude job steps and show only the top‑level job records.
    # -n: remove heather.
    array_cmd = ["sacct", "-X", "-n", "-o", "JobID", "-S", start, "-E", end]
    if user:
        array_cmd+=["-u", user]
    else:
        array_cmd+=["-a"]
    if partition:
        array_cmd+=["-r", partition]

    returncode, stderr, stdout = installib.runBash(array_cmd)
    if returncode!=0:
        print(f"ERROR: could not get jobID: {stderr}")
        return None
    
    return [val.strip() for val in stdout.strip().splitlines()]

# Returns a new DF with only two columns: Field, Value
# Value is the value in the first non empty column for that field in the original df
def simplify_dataFrame(df: pd.DataFrame):
    rows = []
    for row in df.itertuples():
        field = row.Field
        value = next((v for v in row[2:] if v not in ("", None)), None)
        rows.append([field, str(value)])

    return pd.DataFrame(rows, columns=["Field", "Value"])

def printJobStats(jobID: str, df: pd.DataFrame):
    print(f"\nJob statistics for {jobID}:\n")
    out = simplify_dataFrame(df)
    print(out.to_markdown(index=False))

    return out

def getJobsFromDate(submit_date: str, stopped: bool, *, netID: str="", save: bool=False, output_file: str="", partition: str="", start_time: str="00:00:00", end_time: str="23:59:59"):
    print(f"Getting jobs submitted on {submit_date}, from {start_time} to {end_time}.")
    if partition:
        jobs = getJobsID(submit_date, partition=partition, start_time=start_time, end_time=end_time) if not netID else getJobsID(submit_date, user=netID, partition=partition, start_time=start_time, end_time=end_time)
    else:    
        jobs = getJobsID(submit_date, start_time=start_time, end_time=end_time) if not netID else getJobsID(submit_date, user=netID, start_time=start_time, end_time=end_time)
    jobs = [job for job in jobs if job.isdigit() ]

    # Calculate the joint DF with information from all jobs submitted on that date
    all_dfs = []
    for job in jobs:
        if stopped and netID:
            df = get_jobInfo_sacct(job, netID)
        elif stopped:
            df = get_jobInfo_sacct(job)
        else:
            df = get_jobInfo_scontrol(job)

        if not df.empty:
            clean_df = simplify_dataFrame(df)
            clean_df = clean_df.rename(columns={"Value": str(job)})
            all_dfs.append(clean_df)

    if all_dfs:
        joint_df = pd.concat([df.set_index("Field") for df in all_dfs], axis=1).reset_index()

        # Save DF
        if save and output_file:
            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                joint_df.to_excel(writer, sheet_name=submit_date)
            
            strg = f"Information on all jobs that ran on {submit_date}"
            if netID:
                strg+=f" by {netID}"
            strg+=" was saved on: "+os.path.abspath(output_file)
            print(strg)

        return joint_df

    else:
        strg = f"No jobs ran on {submit_date}"
        if netID:
            strg+=f" by {netID}"
        strg+=". No output generated."
        print(strg)

        return pd.DataFrame

def isValidDate(date: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def getQueuePos_notOOD(jobID: str, partition: str):
    cmd1 = ["sprio", "-p", partition, "--sort", "-y"]
    cmd2 = ["awk", "$1=="+jobID+" {print NR-1}"]
    code, stderr, stdout = installib.runPipedCommands([cmd1, cmd2])

    if code!=0:
        return "", stderr
    
    return stdout.replace("\n", ""), stderr

def isInteractive(jobID:str):
    cmd1 = ["scontrol", "show", "job", jobID]
    cmd2 = ["grep", "SubmitLine"]
    code, stderr, stdout = installib.runPipedCommands([cmd1, cmd2])

    if code!=0:
        print(stderr)
        return False
    
    stdout = stdout.strip().replace("SubmitLine=", "")
    return stdout.startswith("srun")

# I know that my job should be pending because there's another interactive app running
def getQueuePos_OOD(netID: str, jobID: str):
    code, stderr, stdout = installib.runBash(["squeue", "-u", netID, "-h", "-o", "%i|%j|%T|%R"])
    if code!=0:
        return "", stderr

    running_interactive = {} # Interactive apps
    queued_interactive = {}

    running_outside_ood = [] # Could be an interactive app (but not necessarily)
    queued_outside_ood = [] # Could be an interactive app (but not necessarily, but for QOSMaxJobsPerUserLimit reason)

    for line in stdout.splitlines():
        line = line.replace("\n", "").split("|")
        if len(line)!=4:
            return "", f"ERROR: unexpected squeue output: {line}"

        id = line[0]
        name = line[1]
        status = line[2]
        reason = line[3].replace("(", "").replace(")", "")
        ood = name.startswith("sys/dashboard")
        qosMax = reason=="QOSMaxJobsPerUserLimit"

        if ood:
            app_name = name.replace("sys/dashboard/sys/bc_hpc_", "")

            if status=="RUNNING":
                running_interactive[id] = app_name
            elif status=="PENDING" and qosMax:
                queued_interactive[id] = app_name
            elif id==jobID:
                return "", f"ERROR: could not find queue position for {jobID}: {line}"

        else:
            if id==jobID:
                return "", f"ERROR: could not find queue position for {jobID}: {line}"
            elif status=="RUNNING":
                running_outside_ood+=[id]
            elif status=="PENDING" and qosMax:
                queued_outside_ood+=[id]

    if jobID not in queued_interactive:
        return "", f"ERROR: could not find queue position for {jobID}"
    
    if len(running_interactive)==0:
        for id in running_outside_ood:
            if isInteractive(id):
                running_interactive[id] = "Interactive app in the Terminal"
    if len(running_interactive)==0:
        return "", f"ERROR: nothing is running inside or outside OOD, {jobID} shouldn't be queued"
    if len(running_interactive)>1:
        return "", f"ERROR: more than one interactive app appears to be running in OOD"
    
    running_id, running_app = next(iter(running_interactive.items()))
    print(f"Job {running_id} is running an interactive app ({running_app}) and blocking the interactive queue for {netID}")

    for id in queued_outside_ood:
        if isInteractive(id):
            queued_interactive[id] = "Interactive app in the Terminal"

    # Get the priority of all queued interactive jobs
    # And order the jobs by priority
    id_prio = {}
    ordered_id = []
    for id in queued_interactive.keys():
        # Get the job priority
        code, stderr, stdout = installib.runBash(["sprio", "-j", id, "-o", "%Y", "-h"])
        if code!=0:
            print(stderr)
            continue

        # Save the job priority
        try:
            priority = int(stdout)
            id_prio[id] = priority
        except:
            print(f"ERROR: wrong priority format for {id} from sprio: {stdout}")
            continue

        # Add the job ID in the ordered list, according to the priority
        insert_pos = len(ordered_id)
        for i in range(len(ordered_id)):
            if priority<id_prio[ordered_id[i]]:
                insert_pos = i
                break
        ordered_id.insert(insert_pos, id)

    # Return the position of jobID in the ordered list by priority
    return str(ordered_id.index(jobID)), ""
    
def getSqueueInfo(netID: str, jobID: str):
    cmd1 = ["squeue", "-u", netID, "-o", "%i|%P|%j|%u|%T|%M|%D|%R"]
    cmd2 = ["grep", jobID]
    code, stderr, stdout = installib.runPipedCommands([cmd1, cmd2])

    if code!=0:
        return "", stderr
    return stdout.replace("\n",""), stderr

def checkPartition(partition: str):
    code, stderr, stdout = installib.runBash(["sinfo", "-p", "normal", "-o", "%D|%t|%N", "-h"])

    if code!=0:
        print(f"ERROR: could not get sinfo in {partition} partition: {stderr}")
        return

    sinfo = stdout.splitlines()
    if len(sinfo)==0:
        print(f"ERROR: could not get sinfo in {partition} partition")
        return

    for line in sinfo:
        array = line.split("|")
        if len(array)!=3:
            print(f"ERROR: could not parse sinfo output line: {line}")
            continue

        print(f"{array[0]} nodes are in {array[1]} state: {array[2]}")
        input("To check what jobs are running in any of those nodes: squeue | grep <node> [Enter]")

def maintenanceEmail(window: str, netID: str, jobID: str):
    print("Send the user the following email:\n")

    print(f"""
    Hello {netID},

    Job {jobID} is currently queued because of an upcoming/scheduled system maintenance window.
    This is happening on {window}.

    Jobs whose requested wall time would extend beyond the maintenance start time, will not begin execution until maintenance has been completed. This is done to ensure jobs are not interrupted by the scheduled outage.

    If possible, you can modify and resubmit your job with a shorter wall time request. Or you can leave the job in queue and it will start running once maintenance has ended and compute resources become available again.

    As a reminder, maintenance notifications are displayed when you connect to the cluster via SSH or access it through Open OnDemand. We also send an email a week before. Please review these messages carefully, as they contain important information including the maintenance start and end times, along with other cluster announcements that may affect your work.

    If you have any questions about your job's wall time requirements or scheduling, please let us know.

    Thanks,
    RCC
    """)

def priorityEmail(jobID: str, netID: str, info: str):
    print("Send the user the following email:\n")

    print(f"""
    Hello {netID},
    
    Job {jobID} is currently queued because because other jobs in the system have a higher scheduling priority at this time. This is normal behavior on a shared HPC cluster and does not indicate a problem with your job.

    {info}

    The scheduler determines job priority using several factors, including the requested resources and the resources that the user has used the past days. To ensure fair use of cluster resources, users who have consumed a larger share of the cluster in recent days may see reduced scheduling priority compared to users who have used fewer resources. This helps provide equitable access to the system for all users.

    At this time, no action is necessarily required. Your job will continue to accrue priority while it remains in the queue and will start automatically when sufficient resources become available and its priority allows it to be scheduled.

    However, if you want to increase your priority and have your jobs run faster, I would suggest checking if you are requesting more resources than needed in your scripts. You can send us some of the scripts that you use the most and we can check if there is a more efficient way for you to request resources. You can also reduce the resources requested in the current job and re-submit, which can sometimes improve scheduling opportunities.

    Thanks,
    RCC
    """)

def getJobStats(jobID: str, netID: str, queued: bool, stopped: bool):
    # The job finished running or failed
    if stopped:
        df = get_jobInfo_sacct(jobID, netID)

    # The job is running
    elif not queued:
        df = get_jobInfo_scontrol(jobID)
        if df.empty:
            print(f"\nMaybe job {jobID} already stopped. Trying with sacct.")
            df = get_jobInfo_sacct(jobID, netID)
            if not df.empty:
                stopped = True

    # The job is queued
    else:
        submit_date = input("\nWhen was the job submitted? (YYYY-MM-DD) [Enter if not known or today]: ")
        if not isValidDate(submit_date):
            print("Not a valid date entered, using today as submission date.")
            submit_date = datetime.now().strftime("%Y-%m-%d")

        # Get information from squeue
        stdout, stderr = getSqueueInfo(netID, jobID)
        if stdout=="":
            if stderr!="":            
                print(stderr)
            else:
                print(f"ERROR: did not find job {jobID} from {netID} in queue")
            return pd.DataFrame, stopped
        
        stdout = stdout.split("|")
        if len(stdout)!=8:
            print(f"ERROR: cant parse squeue output: {stdout}")
            return pd.DataFrame, stopped

        name = stdout[2]
        partition = stdout[1] if not name.startswith("sys/dashboard") else "ood"
        status = stdout[4]
        reason = stdout[7].replace("(", "").replace(")", "")

        if status=="RUNNING":
            print(f"Good news! Job {jobID} is now running!")
            return get_jobInfo_scontrol(jobID), False
        
        if reason in ["Priority", "Resources", "QOSMaxJobsPerUserLimit"]:
            if reason=="Resources":
                print(f"Job {jobID} is waiting for resources to come available.")
                code, stderr, stdout = installib.runBash(["sprio", "-h", "-j", jobID, "-o", "%i|%r|%Y|%S|%A|%F|%J|%Q|%T"])

                if code!=0:
                    print(f"ERROR: could not run sprio on job {jobID}: {stderr}")
                else:
                    stdout = stdout.replace("\n", "")
                    stdout_arr = stdout.split("|")
                    if len(stdout_arr)!=9:
                        print(f"ERROR: could not parse the output of sprio on job {jobID}: {stdout}")
                    else:
                        tres = stdout_arr[8]
                        print(f"Job is requesting the following resources: {tres}")

                        # Check how busy nodes are in a specific partition
                        checkPartition(stdout_arr[1])
                        print("Ask the user to send you the script to see if they can request resources differently.")
                        print("Remind the user that the more resources they request, the longer queue wait times they will have.")

            else:
                if partition=="ood":
                    stdout, stderr = getQueuePos_OOD(netID, jobID)
                else:
                    stdout, stderr = getQueuePos_notOOD(jobID, partition)

                if reason=="QOSMaxJobsPerUserLimit":
                    print(f"Job {jobID} is queued because {netID} has reached the number of running jobs allowed per user for {partition}.")                

                    if stderr!="":
                        print(f"ERROR: could not get the queue position for {jobID}: {stderr}")
                        return

                    if int(stdout)==0:
                        print(f"Job {jobID} is the next in queue and will run as soon as the current interactive job is done.")
                    else:
                        print(f"There are {stdout} jobs in queue ahead of {jobID}. {jobID} will run after the current interactive job, and those ahead are done.")

                else:
                    print(f"""
                    Job {jobID} is queued because of its Priority.
                    Check the user ({netID}) usage the week before submission date to see if the user is being requesting many resources and it's affecting their jobs priority.
                    """)
                    if int(stdout)==0:
                        priorityEmail(jobID, netID, f"Job {jobID} is the next in queue according to its priority for the {partition} partition.")
                    else:
                        priorityEmail(jobID, netID, f"There are {stdout} jobs in queue ahead of {jobID} according to their priority. {jobID} will run once those get assigned their resources.")

        if reason=="Maintenance":
            print(f"Job {jobID} is queued because of the upcoming maintenance.")
            window = input("When does maintenance start? (i.e. April 2, 2025 from 9am-5pm): ")
            maintenanceEmail(window, netID, jobID)

        if "Dependency" in reason:
            print(f"Job {jobID} is queued because one or more dependencies are not satisfied: {reason}")
            print("Send link to video about creating advanced SLURM scripts, which has a section on dependencies: https://youtu.be/-4mBhe5cK7o?si=VyaPi9XtiiduWXR6")

        df = pd.DataFrame

    return df, stopped

def checkOODlogs(job_col: str, df: pd.DataFrame, netID: str):
    app_name = job_col.replace("OOD_", "")
    print(f"\nThis job ran in OOD: {app_name}")

    # Check the session log
    input("\nIn a different Terminal, login as root [Enter]")
    workdir_value = df.loc[df["Field"] == "WorkDir", job_col].iloc[0]
    input(f"vi {workdir_value}/output.log [Enter]")

    # Impersonate the user
    input("\nGo to KeyCloack in Google Chrome [Enter]")
    input("Login as admin [Enter]")
    input(f"Manage realms > ondemand > users > search '{netID}' > click on user > Action > Impersonate [Enter]")
    input("https://ondemand.rcc.mcw.edu/ [Enter]")
    input(f"Sign out as '{netID}' from OnDemand and KeyCloak [Enter]")

    # Edit the app if needed
    if input("\nDo you need to edit something in the OnDemand app? [y/N]: ").strip().lower() in ["y", "yes"]:
        input("Open the Finder [Enter]")
        input("Mount qfs2 SMB [Enter]")
        input("Open KeePass [Enter]")
        input("Linux > Root > ondemand.rcc.mcw.edu > get root password (do NOT close KeePass) [Enter]")
        input("In a different Terminal: ssh root@ondemand.rcc.mcw.edu [Enter]")
        input("Close KeePass [Enter]")
        input(f"vi /var/www/ood/apps/sys/{app_name}/template/script.sh.erb [Enter]")

def checkLogs(df: pd.DataFrame, job_col: str):    
    if "StdErr" in df["Field"].values:
        stdErr = df.loc[df["Field"] == "StdErr", job_col].iloc[0]
        with open(stdErr, "r") as f:
            contentErr = f.read()
    else:
        contentErr = ""

    if "StdOut" in df["Field"].values:
        stdOut = df.loc[df["Field"] == "StdOut", job_col].iloc[0]
        with open(stdOut, "r") as f:
            contentOut = f.read()
    else:
        contentOut = ""
        
    if ("No space left on device" in contentErr) or ("No space left on device" in contentOut):
        nodes = df.loc[df["Field"] == "NodeList", job_col].iloc[0]
        print(f"""\n'No space left on device' error found in the logs.
            Check if the /tmp folder is full in {nodes}.""")
        input("Enter")

    print(f"""\nContent of error log:
    {contentErr}""")
    input("[Enter]")

    print(f"""\nContent of output log:
    {contentOut}""")
    input("[Enter]")

def checkHomeDir(netID: str):
    input("\nIn a different Terminal, login as root (if you haven't done so) [Enter]")
    input(f"su - {netID} [Enter]")
    input(f"mydisks [Enter]")
    if input("Is the home directory full? [y/N]: ").strip().lower() in ["y", "yes"]:
        input("https://qfs2.rcc.mcw.edu/login [Enter]")
        input("Login as your user (include mcwcorp) [Enter]")
        input("Analytics > Capacity Explorer > homefs > check which subfolders are filling the home directory [Enter]")

        if input("Do you want to continue investigating further? [y/N]: ").lower().strip() not in ["y", "yes"]:
            input("Log off the user [Enter]")
            sys.exit(0)
    input("Log off the user [Enter]")

def interactiveTests(stopped: bool, df: pd.DataFrame, job_col: str, jobID: str, netID: str):    
    if stopped:            
        partition = input("What partition was the job running in? (default: normal): ") or "normal"
        job_time = input("Job time (default 01:00:00): ") or "01:00:00"
        ntasks = input("# of threads (default 1): ") or "1"
        mem = input("Amount of memory (default 7.5gb): ") or "75gb"
        ticket = input("Ticket #: ")
        num_cpus = int(df.loc[df["Field"] == "AllocCPUS", job_col].iloc[0])
            
        # srun can't run as root
        input("In a Terminal, logged as root, copy any files you will need to YOUR rccadmin scratch [Enter]")
        input(f"In a Terminal, logged as YOUR user: screen -S ticket_{ticket} [Enter]")
        input(f"srun --ntasks={ntasks} --time={job_time} --job-name=ticket_{ticket} --account=rccadmin --partition={partition} --mem={mem} --pty bash [Enter]")

    else:
        num_cpus = int(df.loc[df["Field"] == "AllocTRES", job_col].iloc[0].split(",")[0].replace("cpu=",""))
        input(f"srun --jobid={jobID} --pty bash [Enter]")

    input(f"""
    Options:
    - Run commands preceded by 'time ' if needed.
    - Run commands or script preceded by 'strace -o output.txt --failed-only '.
    - Run 'top -i -u {netID}' (-i to hide zombie or idle processes):
        - Gives the processes running from {netID} on the compute node.
        - If the load average is higher than the number of CPUs ({num_cpus}), that will mean that all cores are being used, and some processes are waiting for CPU time. That could explain some of longer run times.
        - Check how many jobs are running and how many are sleeping (waiting for CPU to become available).
    [Enter]
    """)
        
    if input("\nDo you want to continue investigating further? [y/N]").lower().strip() not in ["y", "yes"]:
        sys.exit(0)

def checkSystemLogs(jobID: str, df: pd.DataFrame, job_col: str, uid: str):
    print("\nCheck the Slurm job completion log:")
    input("ssh hn01 [Enter]")
    input("ssh sn01 [Enter]")
    input("sudo su - [Enter]")
    input(f"grep {jobID} /var/log/slurm/slurmctld.log [Enter]")

    node_list = df.loc[df["Field"] == "NodeList", job_col].iloc[0]
    print(f"\nCheck logs in the specific nodes ({node_list}):")
    for node in node_list.split(","):
        print(f"Log into {node}:")
        print(f"- Option 1: from a login node: ssh {node} > sudo su -")
        print(f"- Option 2: go back to hn01, sudo, then: scyld-nodectl -i {node} ssh")
        input(f"grep {jobID} /var/log/messages [Enter]")
        searches = ["kill", "oom", "error"]
        if node.startswith("gn"):
            searches+=["nvidia"]
        for search in searches:            
            input(f"grep -Ei '{search}.*(job_'{jobID}'|UID='{uid}'|uid='{uid}')' /var/log/messages [Enter]")
        print("\n")

# mem_str looks like "118.85G"
def to_gigabytes(mem_str: str):
    UNIT_MULTIPLIER = {"K": 1e-6, "M": 1e-3, "G": 1, "T": 1e3, "P": 1e6}
    value, unit = parseMem(mem_str)
    return value * UNIT_MULTIPLIER[unit]

def plot_reqVSused_resources(requested: list[float], used: list[float], title: str, ylabel: str, file_path: str):
    x = np.arange(1, len(requested)+1)
    plt.figure(figsize=(12, 6))

    # Plot requested resources
    plt.plot(x, requested, label="Requested Memory (GB)", color="blue", linewidth=2)

    # Plot used resources
    plt.plot(x, used, label="Used Memory (GB)", color="red", linewidth=2)

    # Shade between the two lines
    plt.fill_between(x, used, requested, where=(np.array(requested) >= np.array(used)), color="lightgray", alpha=0.5)

    plt.xlabel("Job Index")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend(loc="upper left", bbox_to_anchor=(1, 1))
    plt.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(file_path, dpi=200)
    plt.close()

def find_first_crossing(values, threshold):
    for i in range(1, len(values)):
        y1, y2 = values[i-1], values[i]
        if (y1 < threshold and y2 >= threshold) or \
           (y1 > threshold and y2 <= threshold):
            return i + 1  # x index (since x starts at 1)
    return None

def find_first_crossing_interp(values, threshold):
    for i in range(1, len(values)):
        y1, y2 = values[i-1], values[i]
        if (y1 - threshold) * (y2 - threshold) <= 0 and y1 != y2:
            return i + (threshold - y1) / (y2 - y1)
    return None

def plot_pctUsed_resources(percentages: list[float], title:str, ylabel: str, file_path: str, pct_closeToLimit: int, pct_waste: int, vert_lines: bool=False):
    x = np.arange(1, len(percentages)+1)
    plt.figure(figsize=(12, 6))

    # Main line: actual resource usage %
    plt.plot(x, percentages, label="Used (% of Requested)", color="black", linewidth=2)

    # 0–pct_waste% → light red (over-requesting)
    plt.axhline(pct_waste, color="red", linestyle="--", linewidth=1.5, label=f"{pct_waste}% (Wasting resources)")
    plt.fill_between(x, 0, pct_waste, color="lightcoral", alpha=0.3)

    xc_blue = xc_red = None
    if pct_closeToLimit>0:
        # >100% → red (hit memory limit)
        plt.fill_between(x, 100, np.maximum(percentages, 100), where=(np.array(percentages) > 100), color="red", alpha=0.3)
        plt.axhline(100, color="red", linestyle="--", linewidth=1.5, label="100% (Hits limit)")

        # pct_closeToLimit–100% → blue (close to limit)
        plt.axhline(pct_closeToLimit, color="blue", linestyle="--", linewidth=1.5, label=f"{pct_closeToLimit}% (close to Limit)")
        plt.fill_between(x, pct_closeToLimit, 100, color="lightblue", alpha=0.3)

        if vert_lines:
            # Vertical line where resources are close to the limit
            xc_blue = find_first_crossing(percentages, pct_closeToLimit)
            if xc_blue is not None:
                plt.axvline(x=xc_blue, color="blue", linestyle=":", linewidth=2)

            # Vertical line where resources are wasted
            xc_red = find_first_crossing(percentages, pct_waste)
            if xc_red is not None:
                plt.axvline(x=xc_red, color="red", linestyle=":", linewidth=2)

    plt.xlabel("Job Index")
    plt.ylabel(ylabel)
    plt.title(title)

    xticks = list(plt.xticks()[0])
    extra_ticks = [x for x in [xc_blue, xc_red] if x is not None]
    xticks.extend(extra_ticks)
    xticks = sorted(set(xticks))
    labels = [f"{int(x)}" if x == int(x) else f"{x:.1f}" for x in xticks]
    plt.xticks(xticks, labels)
    plt.xlim(1, len(percentages))

    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left", bbox_to_anchor=(1, 1))
    plt.tight_layout()

    plt.savefig(file_path, dpi=200)
    plt.close()

def analyzeBigDF(df: pd.DataFrame, outputs: list[str], titles: list[str], sort: str=""):
    #################################
    ### Plot memory usage metrics ###
    #################################
    MaxRSS_row = df.loc[df["Field"] == "MaxRSS"].iloc[0, 1:].tolist()
    # Get MaxRSS without the percentage values
    rss_values = [x.split(" (")[0] for x in MaxRSS_row]
    # Normalize units for rss_values
    rss_gb = [float(to_gigabytes(x)) for x in rss_values]
    ReqTRES_row = df.loc[df["Field"] == "ReqTRES"].iloc[0, 1:].tolist()
    reqmem = [x.split(",")[1].replace("mem=", "") for x in ReqTRES_row]
    # Normalize units for reqmem
    reqmem_gb = [float(to_gigabytes(x)) for x in reqmem]
    # Get only the percentages
    rss_pct = [float(x.split(" (")[1].split("%")[0]) for x in MaxRSS_row]

    df = df.copy()

    if sort=="mem":
        # Get order indices (sorted by rss_pct descending)
        sorted_idx = sorted(range(len(rss_pct)), key=lambda i: rss_pct[i], reverse=True)

        # Sort the jobs according to rss_pct
        job_cols = df.columns[1:]
        sorted_cols = [job_cols[i] for i in sorted_idx]
        df = df[["Field"] + sorted_cols]
        
        # Sort the arrays for plotting
        reqmem_gb = [reqmem_gb[i] for i in sorted_idx]
        rss_gb    = [rss_gb[i] for i in sorted_idx]
        rss_pct = [rss_pct[i] for i in sorted_idx]

    plot_reqVSused_resources(reqmem_gb, rss_gb, titles[0], "Memory (GB)", outputs[0])
    plot_pctUsed_resources(rss_pct, titles[1], "Memory Used (% of Requested)", outputs[1], 70, 30, True)
    
    # Add the new row with rss percentages
    df.loc[len(df)] = ["RSS_pctg"]+rss_pct

    ###########################
    ### Plot WallTime usage ###
    ###########################
    RunTime = df.loc[df["Field"] == "RunTime"].iloc[0, 1:].tolist()
    runtime_pct = [float(x.split(" ")[1].replace("(", "").replace("%", "")) for x in RunTime]    
    plot_pctUsed_resources(runtime_pct, titles[2], "Time Used (% of WallTime Requested)", outputs[2], 80, 20)

    # Add the new row with runtime percentages
    df.loc[len(df)] = ["RunTime_pctg"]+runtime_pct

    ######################
    ### Plot CPU usage ###
    ######################
    CPUpct = [ float(x) for x in df.loc[df["Field"] == "CPUpct"].iloc[0, 1:].tolist()]
    plot_pctUsed_resources(CPUpct, titles[3], "CPU Used (% of Requested)", outputs[3], -1, 50)

    return df

def checkUserUsage(start_date_str: str, end_date_str: str, netID: str, file_path: str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    all_dfs = {}
    all_cols = {}
    current = start_date

    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        joint_df = getJobsFromDate(date_str, True, netID=netID)

        if not joint_df.empty:
            all_dfs[date_str] = joint_df

            for col in list(joint_df.columns):
                if col!="Field":
                    if not (col in all_cols):
                        all_cols[col] = date_str
                    else:
                        # Get the previous DF from the previous date running the same jobID
                        other_date = all_cols[col]
                        other_df = all_dfs[other_date]

                        # Remove that jobID column from the previous DF to keep the jobID only in the current one
                        other_df = other_df.drop(col, axis=1)
                        all_cols[col] = date_str
                        all_dfs[other_date] = other_df

        current += timedelta(days=1)

    if all_dfs:
        list_dfs = list(all_dfs.values())
        big_df = pd.concat([df.set_index("Field") for df in list_dfs], axis=1).reset_index()

        if file_path.endswith("/"):
            file_path = file_path[:-1]
        plots_paths = [
            os.path.dirname(file_path)+f"/CMP_memoryUsage1_{netID}.png",
            os.path.dirname(file_path)+f"/CMP_memoryUsage2_{netID}.png",
            os.path.dirname(file_path)+f"/CMP_wallTimeUsage_{netID}.png",
            os.path.dirname(file_path)+f"/CMP_CPUUsage_{netID}.png",

            os.path.dirname(file_path)+f"/FL_memoryUsage1_{netID}.png",
            os.path.dirname(file_path)+f"/FL_memoryUsage2_{netID}.png",
            os.path.dirname(file_path)+f"/FL_wallTimeUsage_{netID}.png",
            os.path.dirname(file_path)+f"/FL_CPUUsage_{netID}.png"
            ]
        plots_titles = [
            "Requested vs Used Memory per Completed Jobs",
            "Memory Usage Efficiency Across Completed Jobs",
            "Wall Time use Across Completed Jobs",
            "CPU used Across Completed Jobs",

            "Requested vs Used Memory per Failed Jobs",
            "Memory Usage Efficiency Across Failed Jobs",
            "Wall Time use Across Failed Jobs",
            "CPU used Across Failed Jobs"
            ]

        # Filter DF to keep only completed jobs
        completed_cols = [col for col in big_df.columns[1:] if big_df.loc[big_df["Field"] == "JobState", col].item() == "COMPLETED"]
        comp_df = big_df[["Field"] + completed_cols]
        
        # Generate plots for completed jobs
        comp_df = analyzeBigDF(comp_df, plots_paths[0:4], plots_titles[0:4], "mem")

        # Filter DF to keep only failed jobs
        failed_cols = [col for col in big_df.columns[1:] if big_df.loc[big_df["Field"] == "JobState", col].item() == "FAILED"]
        fail_df = big_df[["Field"] + failed_cols]

        # Generate plots for failed jobs
        fail_df = analyzeBigDF(fail_df, plots_paths[4:8], plots_titles[4:8], "mem")

        # Save everything in excel
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            big_df.to_excel(writer, sheet_name=f"AllJobs")
            comp_df.to_excel(writer, sheet_name=f"CompletedJobs")
            fail_df.to_excel(writer, sheet_name=f"FailedJobs")

            # Adjust column size in sheets
            for sht in "AllJobs", "CompletedJobs", "FailedJobs":
                worksheet = writer.sheets[sht]
                for col_idx, col in enumerate(big_df.columns):
                    max_len = max(big_df[col].astype(str).map(len).max(), len(col))
                    worksheet.set_column(col_idx, col_idx, max_len)

            workbook = writer.book
            for i, plot_path in enumerate(plots_paths):
                if os.path.isfile(plot_path):
                    if i<4:
                        sheet_name = f"CompletedJobs_plot{i+1}"
                    else:
                        sheet_name = f"FailedJobs_plot{i-3}"
                    worksheet = workbook.add_worksheet(sheet_name)
                    worksheet.insert_image("A1", plot_path)

                else:
                    print(f"could not generate plot with {plots_titles[i]}")

        if os.path.isfile(file_path):
            print(f"Summary of all jobs submitted by {netID} between {start_date_str} and {end_date_str} was successfully saved in {file_path}.")
        else:
            print(f"Could not save summary all jobs submitted by {netID} between {start_date_str} and {end_date_str}.")

        for plot in plots_paths:
            if os.path.isfile(plot):
                os.remove(plot)

        return big_df
    
    return pd.DataFrame

def main():
    # Make sure I'm NOT root (sacct and scontrol wont work as root)
    if getpass.getuser()=="root":
        print("Can't run this script as root")
        sys.exit(1)

    # Get arguments
    jobID, netID, submitDate, stopped, queued, outdir = parse_arguments()
    if not jobID:
        jobs = getJobsID(submitDate, user=netID)

        if not jobs:
            print("ERROR: missing jobID")
            sys.exit(1)

        if len(jobs)>1:
            # If jobID is missing submitDate wont be missing, otherwise it would have failed in parse_arguments
            print(f"{len(jobs)} jobs were submitted by {netID} on {submitDate}:\n")
            getJobsFromDate(submit_date, stopped, netID=netID, save=True, output_file=f"{outdir}/{submit_date}.xlsx")
            jobID = input("Choose one job to investigate ([Enter] for the first): ").strip() or jobs[0]

        else:
            jobID = jobs[0]

    # Get job statistics
    df, stopped = getJobStats(jobID, netID, queued, stopped)
    if df.empty:
        if not queued:
            print("ERROR: could not get job info")
        sys.exit(1)

    else:
        # Print job statistics
        simple_df = printJobStats(jobID, df)
        if stopped:
            try:
                print("\n")

                MaxRSS = simple_df.loc[simple_df["Field"] == "MaxRSS", "Value"].iloc[0]
                pct = float(MaxRSS.split(" ")[1].replace("(", "").replace("%", ""))
                if pct>=100:
                    print(f"Memory efficiency is {pct}%. The job hit the memory limit.")
                    print("The user can use python -m memory_profiler script.py if it's a python script to see what parts of the code are using more memory.")
                elif pct>70:
                    print(f"Memory efficiency is {pct}%. The job was close to the limit and could easily OOM on other inputs.")
                elif pct<30:
                    print(f"Memory efficiency is {pct}%. The user is over-requesting memory.")

                if pct<100:
                    RunTime = simple_df.loc[simple_df["Field"] == "RunTime", "Value"].iloc[0]
                    pct = float(RunTime.split(" ")[1].replace("(", "").replace("%", ""))
                    if pct>80:
                        print(f"The job ran in {pct}% of the requested wall time. It could hit wall time in future runs.")
                    elif pct<20:
                        print(f"The job ran in {pct}% of the requested wall time. The user is over-requesting wall time.")

                # If CPU efficiency is far below 100%, the job is not using all allocated cores.
                CPUpct = float(simple_df.loc[simple_df["Field"] == "CPUpct", "Value"].iloc[0])
                AllocCPUS = int(simple_df.loc[simple_df["Field"] == "AllocCPUS", "Value"].iloc[0])
                CPUused = round(AllocCPUS*CPUpct*100)
                if CPUpct<5:
                    print(f"This job is single threaded. It is requesting {AllocCPUS} CPUs, but using {CPUused}. CPU efficiency is {CPUpct}%. Ask the user to request only one CPU.")
                elif CPUpct<20:
                    print(f"There's a high chance that the job is single threaded. The user is requesting {AllocCPUS} CPUs, but using {CPUused}. CPU efficiency is {CPUpct}%. Check the code to make sure it's multi-threaded.")
                elif CPUpct<50:
                    print(f"There's a high chance the job is multi threaded, but it's using less CPUs ({CPUused}) than those requested ({AllocCPUS}).")                
                
            except:
                pass
        input("[Enter]")

        # Check if the job ran in OOD
        job_col = df.columns.values.tolist()[1]
        if job_col.startswith("OOD"):
            checkOODlogs(job_col, df, netID)

        # If not, check the normal logs
        else:
            print(f"Run: jobstats {jobID}")
            CPUpct = input("CPU efficiency (CPU utilization per node): ").replace("%", "")
            try:
                CPUpct = float(CPUpct)
            except:
                print("Not a valid value, can't calculate the number of CPU being used.")

            AllocTRES = simple_df.loc[simple_df["Field"] == "AllocTRES", "Value"].iloc[0]
            if not AllocTRES.startswith("cpu="):
                print(f"Can't calculate the number of CPU being used. AllocTRES: {AllocTRES}.")

            AllocCPUS = int(AllocTRES.split(",")[0].replace("cpu=", ""))
            CPUused = round(AllocCPUS*CPUpct/100)
            if CPUpct<5:
                print(f"This job is single threaded. It is requesting {AllocCPUS} CPUs, but using {CPUused}. CPU efficiency is {CPUpct}%. Ask the user to request only one CPU.")
            elif CPUpct<20:
                print(f"There's a high chance that the job is single threaded. The user is requesting {AllocCPUS} CPUs, but using {CPUused}. CPU efficiency is {CPUpct}%. Check the code to make sure it's multi-threaded.")
            elif CPUpct<50:
                print(f"There's a high chance the job is multi threaded, but it's using less CPUs ({CPUused}) than those requested ({AllocCPUS}).")

            input("From the output of jobstats you can also check memory efficiency (CPU memory usage per node) to see if the user is over requesting memory. [Enter]")

            if (input("\nIs the job running on GPU nodes? [y/N]: ").strip().lower() in ["y", "yes"]) and (input("Did the user requested at least the same number of CPUs as GPUs? [Y/n]: ").strip().lower() in ["n", "no"]):
                print("""That will cause errors. You must reserve at least the same number of CPUs than GPUs.
                    GPUs are used in tandem with a CPU. The CPU executes the main program with the GPU being used at times to carry out specific functions.
                    A CPU is always needed to run a code that uses a GPU.""")
                input("[Enter]")

            checkLogs(df, job_col)

        if input("\nDid you solve the issue? [y/N]: ").lower().strip() in ["y", "yes"]:
            sys.exit(0)

        # Check if home directory is full
        checkHomeDir(netID)

        # Run interactive tests
        if input("\nDo you want to run an interactive job to check the code? [y/N]: ").lower().strip() in ["y", "yes"]:
            interactiveTests(stopped, df, job_col, jobID, netID)
            
        # Check additional logs
        print(f"\nDo NOT run as root: id {netID} [Enter]")
        uid = input("uid (number): ")
        checkSystemLogs(jobID, df, job_col, uid)

        if input("Do you want to continue investigating further? [y/N]: ").lower().strip() not in ["y", "yes"]:
            sys.exit(0)

    # Check other submitted jobs on the same date
    submit_info = df.loc[df["Field"] == "SubmitTime", job_col].iloc[0].split("T")
    submit_date = submit_info[0]
    submit_time = submit_info[1]
    print(f"\nthis job was submitted on {submit_date} {submit_time}")
    selection = input(f"Show jobs on {submit_date}? [u=user, a=all, n=none] (default=n): ").strip().lower()
    if selection in ["u", "user", "a", "all"]:
        sub_select = input(f"""What jobs do you want to see? 
                           Select one:
                           a: Get all jobs submitted on {submit_date}
                           t: Get only jobs submitted around {submit_time}
                           (default=t)""")
        
        if sub_select=="a":
            if selection in ["u", "user"]:
                getJobsFromDate(submit_date, stopped, netID=netID, save=True, output_file=f"{outdir}/tmp.xlsx")
            elif selection in ["a", "all"]:
                getJobsFromDate(submit_date, stopped, save=True, output_file=f"{outdir}/tmp.xlsx")

        else:
            dt = datetime.strptime(f"{submit_date} {submit_time}", "%Y-%m-%d %H:%M:%S")
            before_dt = dt-timedelta(hours=3)
            after_dt = dt+timedelta(hours=3)
            
            info = []
            # If the 6 hour range stays in the same day, just print all jobs in those hours
            if before_dt.date()==dt.date() and after_dt.date()==dt.date():
                start_time = before_dt.strftime("%H:%M:%S")
                end_time = after_dt.strftime("%H:%M:%S")
                info+=[submit_date, start_time, end_time]
            # If the 6 hour range leaks to the day before
            # Print first from before_dt.time the previous day to a second before midnight
            # And then from midnight to after_dt.time on the submission date
            elif before_dt.date()<dt.date():
                before_date = before_dt.date().strftime("%Y-%m-%d")
                start_time = before_dt.strftime("%H:%M:%S")
                into+=[before_date, start_time, "23:59:59"]
                end_time = after_dt.strftime("%H:%M:%S")
                info+=[submit_date, "00:00:00", end_time]
            # If the 6 hour range leaks to the day after
            # print first from before_dt.time to a second before midnight on the submission date
            # And then from midnight to after_dt.time the next day
            else:
                start_time = before_dt.strftime("%H:%M:%S")
                info+=[submit_date, start_time, "23:59:59"]
                after_date = after_dt.date().strftime("%Y-%m-%d")
                end_time = after_dt.strftime("%H:%M:%S")
                info+=[after_date, "00:00:00", end_time]

            i = 0
            for submit_info in info:
                if selection in ["u", "user"]:
                    getJobsFromDate(submit_info[0], stopped, netID=netID, save=True, output_file=f"{outdir}/tmp_{i}.xlsx", start_time=submit_info[1], end_time=submit_info[2])
                elif selection in ["a", "all"]:
                    getJobsFromDate(submit_info[0], stopped, save=True, output_file=f"{outdir}/tmp.xlsx", start_time=submit_info[1], end_time=submit_info[2])
                i+=1

        input(f"scp <YOUR_UID>@login-hpc.rcc.mcw.edu:{outdir}/tmp.xlsx <DESTINATION> [Enter]")

    if input("\nWould you like to investigate the user usage of the cluster during the past week? [y/N]: ").lower().strip() in ["y", "yes"]:
        end_date_str = datetime.now().strftime("%Y-%m-%d")
        start_date_str = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        checkUserUsage(start_date_str, end_date_str, netID, f"{outdir}/{netID}_cluster_usage.xlsx")

    print("Share video on how to troubleshoot jobs: https://youtu.be/XaI2_D2YpRw?si=9BqSRZaj-I_KL1Ca")

if __name__ == "__main__":
    main()