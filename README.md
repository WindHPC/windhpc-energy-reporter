# WindHPC-energy-reporter

The script **energy-reporter.py** reads recorded power data from an InfluxDB, integrates the data and reports the consumed energy per node.

## Getting started

### Dependencies

The energy-reporter requires

* python 3.6 or newer
* the influxdb-client python library version 1.31 or newer

#### Installing dependencies and usage with a python virtual environment (venv)

```sh
python3 -m venv --system-site-packages ~/venvs/WindHPC-energy-reporter
source ~/venvs/WindHPC-energy-reporter/bin/activate
python3 -m pip install -r requirements.txt
```

### Environment setup

The URL and token for the InfluxDB must be provided as environment variables. Additionally, the cluster must be selected due to small differences in the setup. Valid options for `WINDHPC_SYSTEM` are: *TrainingHLRS* and *HSU*

These values can be provided via an `.env` file (preferred)
or as environment variables before running the energy-reporter:

```sh
# .env file content:
INFLUX_URL=<URL>
INFLUX_TOKEN=<TOKEN>
# INFLUX_ORG may be "HLRS" or "WindHPC" (HSU)
INFLUX_ORG=<ORG>
WINDHPC_SYSTEM=<SYSTEM>
```

### Basic usage

The energy-reporter collects energy usage information for a given time period and specified nodes.

On the WindHPC HLRS system the energy data come from an InfluxDB.

**energy-reporter.py** is controlled via the command line:

```sh
energy-reporter.py --start <time_start> --end <time_end> node_0 node_1 node-2 ...
```

time_start and time_end can be provide as ISO 8601 (YYYY-MM-DDThh:mm:ss), epoche (seconds since 1970-01-01 00:00:00 UTC), or the string 'now'

The list of nodes must contain one or more of the nodes for which data shall be obtained from the database. The list of nodes can be provided either via a nodefile (e.g., `$PBS_NODEFILE`) or as individual node names.

At the WindHPC HLRS system, the following nodes are currently available:

* n012001
* n012201
* n012401
* n012601
* n012801


At HSU, the following nodes are available:

* windhpc00
* windhpc01
* windhpc02
* windhpc03
* windhpc04

### Usage in a PBS job script

```sh
#!/bin/bash
#PBS -l ...

# set up environment variables for access to the InfluxDB
export INFLUX_URL="<URL>"
export INFLUX_TOKEN="<TOKEN>"
export INFLUX_ORG="<ORG>"

t_start=$(date +%s)

# run your code/application here

t_end=$(date +%s)

./energy-reporter.py --start $t_start --end $t_end --nodefile $PBS_NODEFILE
```
