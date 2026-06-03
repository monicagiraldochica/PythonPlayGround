#!/usr/bin/env python3.10
import subprocess
import pandas as pd
import re
import os
import installib
import sys
import argparse
from datetime import datetime
import getpass

# Only works for completed jobs
def seff(job_id: str, job_col: str, df: pd.DataFrame):
    # Run seff command
    [returncode, _, stdout] = installib.runBash(["seff", str(job_id)])
    if returncode!=0:
        return df        

    output = stdout.strip() if stdout else ""
    if not output:
        return df

    mem_line = None
    for line in output.splitlines():
        if line.startswith("Memory Efficiency: "):
            mem_line = line.replace("Memory Efficiency: ", "")
            break

    if mem_line is None:
        return df
    
    new_row = {"Field": "MemoryEfficiency", job_col: mem_line}
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

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
    fields = [ "UserId", "JobState", "Reason", "RunTime", "TimeLimit", "SubmitTime", "StartTime", "EndTime", "Partition", "NodeList", "ReqTRES", "AllocTRES", "Command", "StdErr", "StdOut", "WorkDir" ]
    info = [(field, data.get(field, "")) for field in fields]

    # Edit DF
    df = pd.DataFrame(info, columns=["Field", "Value"])
    df = df[~df["Value"].isin([None, '', "(null)", "None"])]
    for col in ["ReqTRES", "AllocTRES"]:
        df.loc[df["Field"]==col, "Value"] = df.loc[df["Field"]==col, "Value"].str.replace(r',billing=.*$', '', regex=True)
    df.loc[df["Field"]=="UserId", "Value"] = df.loc[df["Field"]=="UserId", "Value"].str.replace(r'\(.*$', '', regex=True)

    df = df.reset_index(drop=True)
    return df

# Better to use for failed or completed jobs
def get_jobInfo_sacct(job_id: str):
    fields = [ "User", "JobName", "State", "ExitCode", "DerivedExitCode", "Elapsed", "Timelimit", "Submit", "Start", "End", "Partition", "NodeList", "WorkDir", "ReqCPUS", "AllocCPUS", "ReqMem", "AveRSS", "MaxRSS", "StdOut", "StdErr" ]
    format_str = ",".join(fields)

    try:
        # Run scontrol command
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
    if len(first_line)<len(fields) or len(second_line)<len(fields) or len(third_line)<len(fields):
        return pd.DataFrame()
    df = pd.DataFrame({ "Field": fields, titles[0]: first_line, titles[1]: second_line, titles[2]: third_line })

    # Edit DF
    df = df[df["Field"]!="JobName"] #Remove JobName line since it's already the title of each column
    
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

    # Re-order resources lines
    move_last = [ "AllocCPUS", "AveRSS", "MaxRSS" ]
    mask = df['Field'].isin(move_last)
    df = pd.concat([df[~mask], df[mask]], ignore_index=True)

    # Remove the T from the dates
    job_cols = df.columns.drop('Field')
    fields_to_fix = [ "Submit", "Start", "End" ]
    df.loc[df['Field'].isin(fields_to_fix), job_cols] = df.loc[df['Field'].isin(fields_to_fix), job_cols].apply(lambda col: col.str.replace("T", " "))

    # Add comment to exit codes
    fields_to_fix = [ "ExitCode", "DerivedExitCode" ]
    dic_exitCodes = {
        "0:0":"Success",
        "1:0":"Application error",
        "0:15":"User cancelled job",
        "0:9":"Time limit reached, forced kill, OOM, admin kill",
        "137:0":"Job killed by SIGKILL - could be OOM or timeout",
        "0:271":"Node failure",
        "2:0":"CLI or arg parsing error in script"
    }
    for code,desc in dic_exitCodes.items():
        df.loc[df['Field'].isin(fields_to_fix), job_cols] = df.loc[df['Field'].isin(fields_to_fix), job_cols].apply(lambda col: col.str.replace(code, f"{code} ({desc})"))

    df = df.reset_index(drop=True)
    return df

def parse_arguments():
    parser = argparse.ArgumentParser(description="Troubleshoot a job")
    parser.add_argument("--user", help="netID", required=True)
    parser.add_argument("--stopped", action="store_true", help="Job finished running or failed")

    parser.add_argument("--jobid", help="jobID")
    parser.add_argument("--submit-date", help="Date when job was submitted (YYYY-MM-DD)")

    args = parser.parse_args()
    if not (args.jobid or args.submit_date):
        parser.error("You must provide --jobid and/or --submit-date")
    if args.submit_date:
        try:
            datetime.strptime(args.submit_date, "%Y-%m-%d")
        except ValueError:
            parser.error("submit-date must be in format YYYY-MM-DD")

    return args.jobid, args.user, args.submit_date, args.stopped

def getJobID(user: str, submit_date: str):
    start = f"{submit_date}T00:00:00"
    end = f"{submit_date}T23:59:59"
    returncode, stderr, stdout = installib.runBash(["sacct", "-X", "-n", "-u", user, "-o", "JobID", "-S", start, "-E", end])
    if returncode!=0:
        print(f"ERROR: could not get jobID: {stderr}")
        return None
    return stdout.strip()

def printJobStats(jobID: str, df: pd.DataFrame):
    print(f"\nJob statistics for {jobID}:\n")

    rows = []
    for row in df.itertuples():
        field = row.Field
        value = next((v for v in row[2:] if v not in ("", None)), None)
        rows.append([field, str(value)])

    out = pd.DataFrame(rows, columns=["Field", "Value"])
    print(out.to_markdown(index=False))

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
    jobID, netID, submitDate, stopped = parse_arguments()
    jobID = jobID or getJobID(netID, submitDate)
    if not jobID:
        print("ERROR: missing jobID")
        sys.exit(1)

    # Get job statistics
    if stopped:
        df = get_jobInfo_sacct(jobID)
    else:
        df = get_jobInfo_scontrol(jobID)
        if df.empty:
            print(f"Maybe job {jobID} already stopped. Trying with sacct.")
            df = get_jobInfo_sacct(jobID)
            if not df.empty:
                stopped = True
    if df.empty:
        print("ERROR: could not get job info")
        sys.exit(1)

    # Get job efficiency
    cols = df.columns.values.tolist()
    job_col = cols[1]
    if stopped:
        df = seff(jobID, job_col, df)

    printJobStats(jobID, df)
    input("\n[Enter]")

    # Check if the job ran in OOD
    if job_col.startswith("OOD"):
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
            input(f"vi /var/www/ood/apps/sys/bc_hpc_jupyter/template/script.sh.erb [Enter]")

    # If not, check the normal logs
    else:
        stdErr = df.loc[df["Field"] == "StdErr", job_col].iloc[0]
        if stdErr:
            print(stdErr)
        stdOut = df.loc[df["Field"] == "StdOut", job_col].iloc[0]
        if stdOut:
            print(stdOut)

    if input("\nDid you solve the issue? [y/N]: ").lower().strip() in ["y", "yes"]:
        sys.exit(0)

    # Check if home directory is full
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

    # Run interactive tests
    if input("\ndo you want to run an interactive job to check the code? [y/N]: ").lower().strip() in ["y", "yes"]:
        if stopped:
            input(f"Get user account (NOT as root): id {netID} [Enter]")
            acct = input("User account: ")
            partition = input("What partition was the job running in?: ")
            job_time = input("Job time (HH:MM:SS): ")
            ntasks = input("# of threads: ")
            mem = input("Amount of memory (i.e. 128gb): ")
            ticket = input("Ticket #: ")
            input(f"In the same Terminal, still logged in as {netID}: screen -S ticket_{ticket} [Enter]")
            input(f"srun --ntasks={ntasks} --time={job_time} --job-name=ticket_{ticket} --account={acct} --partition={partition} --mem={mem} --pty bash [Enter]")
        else:
            input(f"srun --jobid={jobID} --pty bash [Enter]")
        input("""
              Options:
              - Run commands preceded by 'time ' if needed.
              - Run commands or script preceded by 'strace -o output.txt --failed-only '.
              - Run 'top'.
              """)
        
    # Check additional logs
    print("\nCheck the Slurm job completion log:")
    input("ssh hn01 [Enter]")
    input("ssh sn01 [Enter]")
    input("sudo su - [Enter]")
    input(f"grep {jobID} /var/log/slurm/slurmctld.log [Enter]")

    node_list = df.loc[df["Field"] == "NodeList", "Value"].iloc[0]
    print(node_list)

if __name__ == "__main__":
    main()