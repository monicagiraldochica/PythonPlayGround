#!/usr/bin/env python3.10
import subprocess
import pandas as pd
import re
import os
import installib
import sys
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
    [returncode, stderr, stdout] = installib.runBash(["scontrol", "show", "job", str(job_id)])
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

# Better to use for failed or completed jobs
def get_jobInfo_sacct(job_id: str, netID: str=""):
    format_str = ",".join(SACCT_FIELDS)

    try:
        # Run acct command
        result = subprocess.run(["sacct", "-j", str(job_id), f"--format={format_str}", "--units=G" , "--noheader", "--parsable2"], capture_output=True, text=True, check=True)

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
    titles = [first_line[1], second_line[1], third_line[1]]
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
        new_vals+=[f"cpu={cpus},mem={mem},node={nodes}"]
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
    fields_to_fix = [ "Submit", "Start", "End" ]
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
    MaxRSS = df.loc[df["Field"] == "MaxRSS", "batch"].iloc[0]
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

def getJobID(submit_date: str, user: str=""):
    start = f"{submit_date}T00:00:00"
    end = f"{submit_date}T23:59:59"

    # -X: exclude job steps and show only the top‑level job records.
    # -n: remove heather.
    if user:
        returncode, stderr, stdout = installib.runBash(["sacct", "-X", "-n", "-o", "JobID", "-S", start, "-E", end, "-u", user])
    else:
        returncode, stderr, stdout = installib.runBash(["sacct", "-X", "-n", "-o", "JobID", "-S", start, "-E", end, "-a"])
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

def getJobsFromDate(submit_date: str, stopped: bool, *, netID: str="", save: bool=False, output_file: str=""):
    jobs = getJobID(submit_date) if not netID else getJobID(submit_date, netID)

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

def getQueuePosition(jobID: str):
    try:
        p1 = subprocess.Popen(["sprio", "-p", "gpu", "--sort", "-y"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        p2 = subprocess.Popen(["awk", "{print NR-1 $0}"], stdin= p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p1.close()

        p3 = subprocess.Popen(["less", "+g", "-p", jobID], stdin=p2.stdout)
        p2.close()
        p3.communicate()

    except Exception as e:
        print("ERROR: sprio failed")

def getJobStats(jobID: str, netID: str, queued: bool, stopped: bool, output: str=""):
    if stopped:
        df = get_jobInfo_sacct(jobID, netID)

    elif not queued:
        df = get_jobInfo_scontrol(jobID)
        if df.empty:
            print(f"Maybe job {jobID} already stopped. Trying with sacct.")
            df = get_jobInfo_sacct(jobID, netID)
            if not df.empty:
                stopped = True

    else:
        submit_date = input("When was the job submitted? (YYYY-MM-DD, [Enter if not known]): ")
        if not isValidDate(submit_date):
            print("Not a valid date entered, using today as submission date.")
            submit_date = datetime.now().strftime("%Y-%m-%d")

        getJobsFromDate(submit_date, True, netID=netID, save=True, output_file=output)
        queue_pos = getQueuePosition(jobID)
        input(f"Job is in position {queue_pos} in queue [Enter]")
        input(f"Get priority of the job: 'sprio -j {jobID}' [Enter]")
        input(f"Check how busy the nodes are: 'sinfo")
        # nodes is obtained in one of the functions, it could be returned and given to this one
        input(f"Check the specific node it is running on: 'scontrol show node <node> | grep AllocTRES'")
        input(f"Check which jobs are running on a node: 'squeue | grep <node>'")

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
    stdErr = df.loc[df["Field"] == "StdErr", job_col].iloc[0]
    if stdErr:
        with open(stdErr, "r") as f:
            contentErr = f.read()
    else:
        contentErr = ""

    stdOut = df.loc[df["Field"] == "StdOut", job_col].iloc[0]
    if stdOut:
        with open(stdOut, "r") as f:
            contentOut = f.read()
    else:
        contentOut = ""
        
    if ("No space left on device" in contentErr) or ("No space left on device" in contentOut):
        nodes = df.loc[df["Field"] == "NodeList", job_col].iloc[0]
        nodes = ",".join(nodes)
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

        if input("Do you want to continue investigating further? [y/N]").lower().strip() not in ["y", "yes"]:
            input("Log off the user [Enter]")
            sys.exit(0)
    input("Log off the user [Enter]")

def interactiveTests(stopped: bool, df: pd.DataFrame, job_col: str, jobID: str):    
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
    - Run 'top -i' (-i to hide zombie or idle processes):
        - If the load average is higher than the number of CPUs ({num_cpus}), that will mean that all cores are being used, and some processes are waiting for CPU time. That could explain some of longer run times.
        - Check how many jobs are running and how many are sleeping (waiting for CPU to become available).
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
    print(f"Check logs in the specific nodes ({','.join(node_list)}):")
    for node in node_list:
        print(f"Option 1: from a login node: ssh {node} > sudo su -")
        print(f"Option 2: go back to hn01, sudo, then: scyld-nodectl -i {node} ssh")
        input(f"grep {jobID} /var/log/messages [Enter]")
        searches = ["kill", "oom", "error"]
        if node.startswith("gn"):
            searches+=["nvidia"]
        for search in searches:            
            input(f"grep -Ei '{search}.*(job_'{jobID}'|UID='{uid}'|uid='{uid}')' /var/log/messages [Enter]")

# mem_str looks like "118.85G"
def to_gigabytes(mem_str: str):
    UNIT_MULTIPLIER = {"K": 1e-6, "M": 1e-3, "G": 1, "T": 1e3, "P": 1e6}
    value, unit = parseMem(mem_str)
    return value * UNIT_MULTIPLIER[unit]

def plot_reqVSused_resources(requested: pd.DataFrame, used: pd.DataFrame, title: str, ylabel: str, file_path: str):
    x = np.arange(1, len(requested)+1)
    plt.figure(figsize=(12, 6))

    # Plot requested resource
    plt.plot(x, requested, label="Requested Memory (GB)", color="blue", linewidth=2)

    # Plot used resource
    plt.plot(x, used, label="Used Memory (GB)", color="red", linewidth=2)

    # Shade between the two lines
    plt.fill_between(x, used, requested, where=(np.array(requested) >= np.array(used)), color="lightgray", alpha=0.5)

    plt.xlabel("Job Index")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(file_path, dpi=200)
    plt.close()

def analyzeBigDF(df: pd.DataFrame, file_path: str, titles: list[str]):
    MaxRSS_row = df.loc[df["Field"] == "MaxRSS"].iloc[0, 1:].tolist()
    rss_pct = [float(x.split(" (")[1].split("%")[0]) for x in MaxRSS_row]
    rss_values = [x.split(" (")[0] for x in MaxRSS_row]
    # Normalize units for rss_values
    rss_gb = [float(to_gigabytes(x)) for x in rss_values]

    ReqTRES_row = df.loc[df["Field"] == "ReqTRES"].iloc[0, 1:].tolist()
    reqmem = [x.split(",")[1].replace("mem=", "") for x in ReqTRES_row]
    # Normalize units for reqmem
    reqmem_gb = [float(to_gigabytes(x)) for x in reqmem]

    plot_reqVSused_resources(reqmem_gb, rss_gb, titles[0], "Memory (GB)", file_path)

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

        # Filter DF to keep only completed jobs
        completed_cols = [col for col in big_df.columns[1:] if big_df.loc[big_df["Field"] == "JobState", col].item() == "COMPLETED"]
        comp_df = big_df[["Field"] + completed_cols]

        # Generate plots for completed jobs
        if file_path.endswith("/"):
            file_path = file_path[:-1]
        plot_path = os.path.dirname(file_path)+f"/memoryUsage1_{netID}.png"
        plot_title = "Requested vs Used Memory per Completed Jobs"
        analyzeBigDF(comp_df, plot_path, [plot_title])
        if os.path.isfile(plot_path):
            print(f"Plot with {plot_title} successfully saved in {plot_path}")
        else:
            print(f"could not generate plot with {plot_title}")

        # Filter DF to keep only failed jobs
        failed_cols = [col for col in big_df.columns[1:] if big_df.loc[big_df["Field"] == "JobState", col].item() == "FAILED"]
        fail_df = big_df[["Field"] + failed_cols]

        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            big_df.to_excel(writer, sheet_name=f"{netID}_AllJobs")
            comp_df.to_excel(writer, sheet_name=f"{netID}_CompletedJobs")
            fail_df.to_excel(writer, sheet_name=f"{netID}_FailedJobs")

        if os.path.isfile(file_path):
            print(f"Summary of all jobs submitted by {netID} between {start_date_str} and {end_date_str} was successfully saved in {file_path}.")
        else:
            print(f"Could not save summary all jobs submitted by {netID} between {start_date_str} and {end_date_str}.")

        return big_df
    
    return pd.DataFrame

def main():
    # Check python version
    if not installib.checkPythonVers(3, 12, 10, True)[0]:
        print("ERROR: This script requires Python 3.12.10\n")
        sys.exit(1)

    # Make sure I'm NOT root (sacct and scontrol wont work as root)
    if getpass.getuser()=="root":
        print("Can't run this script as root")
        sys.exit(1)

    # Get arguments
    jobID, netID, submitDate, stopped, queued, outdir = parse_arguments()
    if not jobID:
        jobs = getJobID(submitDate, netID)

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
    df, stopped = getJobStats(jobID, netID, queued, stopped, f"{outdir}/{jobID}.xlsx")
    if df.empty:
        if not queued:
            print("ERROR: could not get job info")
        sys.exit(1)

    # Print job statistics
    simple_df = printJobStats(jobID, df)
    if stopped:
        try:
            print("\n")

            MaxRSS = simple_df.loc[simple_df["Field"] == "MaxRSS", "Value"].iloc[0]
            pct = float(MaxRSS.split(" ")[1].replace("(", "").replace("%", ""))
            if pct>=100:
                print(f"Memory efficiency is {pct}%. The job hit the memory limit.")
                #python -m memory_profiler script.py if it's a python script to see what parts of the code are using more memory
            elif pct>70:
                print(f"Memory efficiency is {pct}%. The job was close to the limit and could easily OOM on other inputs.")
            elif pct<30:
                print(f"Memory efficiency is {pct}%. The user is over-requesting memory.")

            RunTime = simple_df.loc[simple_df["Field"] == "RunTime", "Value"].iloc[0]
            pct = float(RunTime.split(" ")[1].replace("(", "").replace("%", ""))
            if pct>80:
                print(f"The job ran in {pct}% of the requested wall time. It could hit wall time in future runs.")
            elif pct<20:
                print(f"The job ran in {pct}% of the requested wall time. The user is over-requesting wall time.")

            CPUpct = float(simple_df.loc[simple_df["Field"] == "CPUpct", "Value"].iloc[0])
            AllocCPUS = int(simple_df.loc[simple_df["Field"] == "AllocCPUS", "Value"].iloc[0])
            if CPUpct<5:
                print(f"This job is single threaded but is requesting {AllocCPUS}. CPU efficiency is {CPUpct}%. Ask the user to request only one CPU.")
            elif CPUpct<20:
                print(f"There's a high chance that the job is single threaded, but the user is requesting {AllocCPUS}. CPU efficiency is {CPUpct}%. Check the code to make sure it's multi-threaded.")
            elif CPUpct<50:
                print(f"There's a high chance the job is multi threaded, but it's using less CPUs than those requested ({AllocCPUS}).")
            
            #If this is far below 100%, the job is not using all allocated cores.
        except:
            pass
    input("[Enter]")

    if (input("\nIs the job running on GPU nodes? [y/N]: ").strip().lower() in ["y", "yes"]) and (input("Did the user requested at least the same number of CPUs as GPUs? [Y/n]: ").strip().lower() in ["n", "no"]):
        print("""That will cause errors. You must reserve at least the same number of CPUs than GPUs.
              GPUs are used in tandem with a CPU. The CPU executes the main program with the GPU being used at times to carry out specific functions.
              A CPU is always needed to run a code that uses a GPU.""")
        input("[Enter]")

    # Check if the job ran in OOD
    job_col = df.columns.values.tolist()[1]
    if job_col.startswith("OOD"):
        checkOODlogs(job_col, df, netID)

    # If not, check the normal logs
    else:
        checkLogs(df, job_col)

    if input("\nDid you solve the issue? [y/N]: ").lower().strip() in ["y", "yes"]:
        sys.exit(0)

    # Check if home directory is full
    checkHomeDir(netID)

    # Run interactive tests
    if input("\nDo you want to run an interactive job to check the code? [y/N]: ").lower().strip() in ["y", "yes"]:
        interactiveTests(stopped, df, job_col, jobID)
        
    # Check additional logs
    print(f"Do NOT run as root: id {netID} [Enter]")
    uid = input("uid: ")
    checkSystemLogs(jobID, df, job_col, uid)

    if input("Do you want to continue investigating further? [y/N]").lower().strip() not in ["y", "yes"]:
        sys.exit(0)

    # Check other submitted jobs on the same date
    submit_date = df.loc[df["Field"] == "SubmitTime", job_col].iloc[0].split("T")[0]
    selection = input(f"Show jobs on {submit_date}? [u=user, a=all, n=none] (default=n): ").strip().lower()
    if selection in ["u", "user"]:
        getJobsFromDate(submit_date, stopped, netID=netID, save=True, output_file=f"{outdir}/tmp.xls")
    elif selection in ["a", "all"]:
        getJobsFromDate(submit_date, stopped, save=True, output_file=f"{outdir}/tmp.xls")

    #big_df = checkUserUsage(start_date_str: str, end_date_str: str, netID: str, file_path: str)

if __name__ == "__main__":
    main()