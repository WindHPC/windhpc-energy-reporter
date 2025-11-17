#! /usr/bin/env python3
#
# Copyright (c) 2025       Helmut-Schmidt-Universität/
#                          Universität der Bundeswehr Hamburg.  All rights reserved.
#

import datetime
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

__author__ = "Ruben Horn"


# Must be changed if either of the files are moved or renamed
ENERGY_REPORTER_SCRIPT_PATH = Path(__file__).parent.parent / "energy-reporter.py"


def slurm_time_to_unix(t_fmtd: str) -> Optional[int]:
    if t_fmtd in ("Unknown", "N/A", ""):
        return None
    dt = datetime.datetime.strptime(t_fmtd, "%Y-%m-%dT%H:%M:%S")
    return int(time.mktime(dt.timetuple()))


def get_job_info(
    job_id: str,
) -> Optional[Tuple[Optional[int], Optional[int], List[str]]]:
    # Use sacct to get start and end time
    try:
        result = subprocess.run(
            [
                "sacct",
                "-j",
                str(job_id),
                "--format=JobIDRaw,Start,End,NodeList",
                "--parsable2",
                "--noheader",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running sacct: {e.stderr}", file=sys.stderr)
        return None

    lines = result.stdout.strip().split("\n")
    for line in lines:
        fields = line.split("|")
        if fields[0] == str(job_id):  # Match exact job ID (skip steps like jobid.batch)
            start = slurm_time_to_unix(fields[1])
            end = slurm_time_to_unix(fields[2])
            nodelist = fields[3]
            # Expand node list using scontrol
            node_expansion = subprocess.run(
                ["scontrol", "show", "hostnames", nodelist],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            nodelist = (
                node_expansion.stdout.strip().split("\n")
                if node_expansion.returncode == 0
                else []
            )
            return start, end, nodelist
    return None


def main() -> int:
    if len(sys.argv) < 2 or "--help" in sys.argv or "-h" in sys.argv:
        print(f"Usage: {sys.argv[0]} <job_id> [energy-reporter.py args ...]")
        return os.EX_USAGE

    job_id = sys.argv[1]
    job_info = get_job_info(job_id)
    if job_info is None:
        print(f"Could not load info for job with ID {job_id}", file=sys.stderr)
        return os.EX_USAGE
    start, end, nodelist = job_info
    if start is None or end is None or len(nodelist) == 0:
        print(f"Job with ID {job_id} has not started or not completed", file=sys.stderr)
        return os.EX_TEMPFAIL
    nodelist_str = " ".join(nodelist)
    print("# start: ", start)
    print("# end:   ", start)
    print("# nodes: ", nodelist_str)

    cmd = f"{ENERGY_REPORTER_SCRIPT_PATH.absolute()} --start {start} --end {end} {' '.join(sys.argv[2:])} {nodelist_str}"
    return os.system(cmd)


if __name__ == "__main__":
    sys.exit(main())
