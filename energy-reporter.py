#!/usr/bin/env python3

import os
import sys

if len(sys.argv)<3:
    print("usage: query time_start time_end node_0 node_1 node_2 ...")
    print("time_start and time_end must be in timestamp format (seconds since 1970-01-01 00:00:00 UTC)")
    quit()

#print(sys.argv)
t_start=sys.argv[1]
t_end=sys.argv[2]

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

influx_url = os.getenv('INFLUX_URL')
influx_token = os.getenv('INFLUX_TOKEN')
client = InfluxDBClient(url=influx_url, token=influx_token, org="HLRS")

query_api = client.query_api()


## using Table structure
query='from(bucket:"training") \
        |> range(start: ' + t_start + ' ,stop: ' + t_end + ') \
        |> filter(fn: (r) => r["_measurement"] == "ipmi_sensor") \
        |> filter(fn: (r) => r["name"] == "ps2_input_power") \
        |> map(fn: (r) => ({ r with _time: int(v: r._time)}))'

#print(query)

# tables contains data for all nodes in the specified time frame
tables = query_api.query(query)

# these WINDHPC nodes exist
windhpc_nodes_all = ["n012001", "n012201", "n012401", "n012601", "n012801"]

# fill list with nodes from command line
windhpc_nodes =[]
for i in range(3, len(sys.argv)):
    windhpc_nodes.append(sys.argv[i])

#print (windhpc_nodes)

# loop over nodes
for host_name in windhpc_nodes:
    print("# time_[s] power_[W]_" + host_name)
    energy=0
    t_first_a=-1
    t_first_b=-1
    p_first=-1
    t_last=-1

    # loop over tables
    for table in tables:
        #print(table)
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
