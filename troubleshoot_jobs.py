#!/usr/bin/env python3.10
import subprocess
import pandas as pd
import re
import os

# Only works for running, queued or recently finished jobs
def get_jobInfo_scontrol(job_id):
    """
    Get selected job information from scontrol for a given job ID.
    Returns a pandas DataFrame with columns ['Field', 'Value'].
    Returns an empty DataFrame if job is not found in Slurm memory.
    """
    try:
        # Run scontrol command
        result = subprocess.run(["scontrol", "show", "job", str(job_id)], capture_output=True, text=True, check=True)

    except subprocess.CalledProcessError:
        # Job not found or command failed
        return pd.DataFrame()

    output = result.stdout.strip()
    if not output or "JobId" not in output:
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
def get_jobInfo_sacct(job_id):
    """
    Get selected job information from sacct for a given job ID.
    Returns a pandas DataFrame with columns ['Field', 'Value'].
    Returns an empty DataFrame if no sacct data exists yet.
    """
    fields = [ "User", "JobName", "State", "ExitCode", "DerivedExitCode", "Elapsed", "Timelimit", "Submit", "Start", "End", "Partition", "NodeList", "WorkDir", "ReqCPUS", "AllocCPUS", "ReqMem", "AveRSS", "MaxRSS" ]
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
        first_line[1] = f"OOD {os.path.basename(first_line[1])}"
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
    
#df = get_jobInfo_scontrol()
#print(df)

df = get_jobInfo_sacct(5886414)
print(df)
print("\n")
df = get_jobInfo_sacct(5896738)
print(df)