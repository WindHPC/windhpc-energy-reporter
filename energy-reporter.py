#!/usr/bin/env python3
#
# Copyright (c) 2025       High Performance Computing Center Stuttgart,
#                          University of Stuttgart.  All rights reserved.
#

import argparse
import logging
import os
import re

from datetime import datetime

def parse_time_str(time_str):
    """Parse time from 'now', ISO 8601, or epoch"""
    # parse 'now'
    if time_str.lower() == "now":
        return datetime.now()
    # parse epoche
    if re.match(r"^\d+$", time_str):
        return datetime.fromtimestamp(int(time_str))
    # parse ISO 8601 (YYYY-MM-DDThh:mm:ss) or fail
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}")


def main():
    parser = argparse.ArgumentParser(
        description="%(prog)s: Collects energy data for a given time period on specified computenodes"
        )
    parser.add_argument("--nodefile", type=argparse.FileType('r'), help="nodefile containing nodenames (one node per line)")
    parser.add_argument("-v", "--verbose", help="verbose output", action="store_true")
    parser.add_argument("-V", "--version", help="print version information and exit", action="version", version="%(prog)s 0.1")
    parser.add_argument("--start", help="start time as ISO 8601, epoch or 'now' (default: %(default)s)", default="now")
    parser.add_argument("--end", help="end time as ISO 8601, epoch or 'now' (default: %(default)s)", default="now")
    parser.add_argument("nodelist", nargs="*", help="list of nodenames")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s"
    )

    logging.debug(f"Command line arguments: {args}")

    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS

    influx_url = os.getenv('INFLUX_URL')
    influx_token = os.getenv('INFLUX_TOKEN')
    client = InfluxDBClient(url=influx_url, token=influx_token, org="HLRS")

    query_api = client.query_api()


    t_start = int(parse_time_str(args.start).timestamp())
    t_end = int(parse_time_str(args.end).timestamp())
    query=f"""from(bucket:"training")
            |> range(start: {t_start} ,stop: {t_end})
            |> filter(fn: (r) => r["_measurement"] == "ipmi_sensor")
            |> filter(fn: (r) => r["name"] == "ps2_input_power")
            |> map(fn: (r) => ({{ r with _time: int(v: r._time)}}))"""

    logging.debug(f"Query: {query}")

    # tables contains data for all nodes in the specified time frame
    tables = query_api.query(query)

    # fill list with nodes from command line
    nodes = args.nodelist
    # append nodes from nodefile
    if args.nodefile :
        for line in args.nodefile:
            nodes.append(line.strip())
    logging.debug(f"Nodes: {nodes}")

    # loop over nodes
    for host_name in nodes:
        print("# time_[s] power_[W]_" + host_name)
        energy=0
        t_first_a=-1
        t_first_b=-1
        p_first=-1
        t_last=-1

        # loop over tables
        for table in tables:
            for row in table.records:
                if row["host"] == host_name:
                    # print (row.values)
                    t=int(row["_time"]/1000000000)
                    p=int(row["_value"])
                    print(t,p,row["host"])

                    if t_first_b==-2:
                        t_first_b=t


                    if t_first_a==-1:
                        t_first_a=t
                        p_first=p
                        t_first_b=-2

                    # integrate power
                    if t_first_b>0:
                        energy=energy+row["_value"]*(t-t_last)

                    t_last=t


        # add contribution from first interval
        energy=energy+p_first*(t_first_b-t_first_a)

        print ("host: " + host_name + " energy_[J]: " + str(energy))
        print ("")

if __name__ == "__main__":
    main()
