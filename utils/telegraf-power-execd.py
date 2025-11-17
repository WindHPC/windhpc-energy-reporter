#! /usr/bin/env python3
#
# Copyright (c) 2025       Helmut-Schmidt-Universität/
#                          Universität der Bundeswehr Hamburg.  All rights reserved.
#

"""Input command for providing power related metrics to Telegraph via inputs.execd in InfluxDB line format.
(Must be called as root or by user who can run "/usr/bin/sudo /usr/sbin/ipmi-sensors" without root)

Add to telegraf.conf on each node:
[[inputs.execd]]
  command = ["telegraf-power-execd.py", "1", "pdu_sensor", "1"]
  data_format = "influx"

[[inputs.execd]]
  command = ["telegraf-power-execd.py", "1", "pdu_sensor", "2"]
  data_format = "influx"

[[inputs.execd]]
  command = ["telegraf-power-execd.py", "1", "ipmi_sensor"]
  data_format = "influx"

[[inputs.execd]]
  command = ["telegraf-power-execd.py", "1", "rapl_counter"]
  data_format = "influx"
"""

__author__ = "Ruben Horn"

import json
import math
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path
from subprocess import check_output
from typing import Any, Dict, List, Tuple

PDU_HOSTS = ["windhpc00"]
USE_IPMI_SENSORS_EXTRA_ARGS = False
PSU_IPS = # TODO: Add list of two PDU addresses!


def get_ipmi_power() -> None:
    cmd = ["/usr/bin/sudo", "/usr/sbin/ipmi-sensors"]
    if USE_IPMI_SENSORS_EXTRA_ARGS:
        cmd += ["-t", "Other_Units_Based_Sensor", "--quiet-cache"]
    output = check_output(cmd).decode()
    ks: List[str] = []
    vs: List[str] = []
    for line in output.splitlines():
        line = line.lower()
        if "input power" not in line:
            continue
        columns = line.split("|")
        k = columns[1].strip().replace(" ", "_")
        v = columns[3].strip()
        ks.append(k)
        vs.append(v)
    assert len(ks) == len(vs) == 2
    print(f"{ks[0]}={vs[0]},{ks[1]}={vs[1]}", flush=True)


def get_pdus_power(sensor_name: str, host: str, pdu_number: int) -> None:
    # NOTE: netio PowerPDU 4KS for compute node power input
    assert pdu_number in [1, 2]
    json_str = "{}"
    with urllib.request.urlopen(
        f"http://{PSU_IPS[pdu_number - 1]}/netio.json"
    ) as response:
        json_str = response.read().decode()
    doc = json.loads(json_str)
    for output in doc["Outputs"]:
        # Derive node names:
        # windhpc00 -> e.g. windhpc01 (corresponding to PDU output)
        host = host[:-1] + str(output["ID"])
        print(
            f"{sensor_name},host={host} pdu_{pdu_number}_output_power={float(output['Load'])}",
            flush=True,
        )


def get_rapl_power() -> None:
    # NOTE: Intel Xeon (Cascade Lake) specific
    domain_base_path = "/sys/class/powercap/intel-rapl"
    i = 0

    def get_rapl_domain_values(sysfs_path: Path) -> Tuple[str, float, float]:
        sysfs_path = Path(sysfs_path)
        name = (sysfs_path / "name").read_text().strip()
        energy_uj = int((sysfs_path / "energy_uj").read_text().strip())
        max_energy_range_uj = int(
            (sysfs_path / "max_energy_range_uj").read_text().strip()
        )
        return name, energy_uj, max_energy_range_uj

    def compute_power(rapl_values: Dict[str, Any], timestamp: float) -> None:
        last_values_path = Path(__file__).parent / "rapl_values.json"
        last_values = dict(timestamp=float("nan"), values={})
        if last_values_path.is_file():
            try:
                last_values = json.loads(last_values_path.read_text())
            except Exception:
                pass
        dt = timestamp - float(last_values["timestamp"])  # type: ignore
        for i, k in enumerate(rapl_values):
            last_energy_uj = last_values["values"].get(k, dict(energy_uj=float("nan")))[
                "energy_uj"
            ]
            energy_uj = rapl_values[k]["energy_uj"]
            max_energy_range_uj: float = rapl_values[k]["energy_uj"]
            # Compute delta and account for possible overflow
            denergy_uj = (
                float(energy_uj - last_energy_uj) + max_energy_range_uj
            ) % max_energy_range_uj
            # uJ/s -> uWs/s -> uW -> W/10**6
            power_w = (denergy_uj / dt) / 10**6
            if i > 0:
                print(",", end="")
            if math.isnan(power_w):
                power_w = 0  # Telegraph/InfluxDB does not support NaN in row format?
            print(f"rapl_{k}_derived_power={power_w}", end="")
        last_values_path.write_text(
            json.dumps(dict(timestamp=timestamp, values=rapl_values), indent=3)
        )
        pass

    rapl_values = {}
    timestamp = time.time()
    while True:
        package_domain = Path(domain_base_path + f":{i}")
        dram_domain = Path(domain_base_path + f":{i}:0")
        if not package_domain.is_dir():
            break
        name, energy_uj, max_energy_range_uj = get_rapl_domain_values(package_domain)
        rapl_values[name] = dict(
            energy_uj=energy_uj, max_energy_range_uj=max_energy_range_uj
        )
        name2, energy_uj, max_energy_range_uj = get_rapl_domain_values(dram_domain)
        rapl_values[f"{name}_{name2}"] = dict(
            energy_uj=energy_uj, max_energy_range_uj=max_energy_range_uj
        )
        i += 1
    compute_power(rapl_values, timestamp)
    print(flush=True)


def run_one(sensor: str) -> None:
    host = socket.gethostname().split(".")[0]
    if sensor == "pdu_sensor" and host not in PDU_HOSTS:
        return
    if sensor == "ipmi_sensor":
        print(f"{sensor},host={host}", end=" ")
        get_ipmi_power()
    elif sensor == "pdu_sensor":
        assert len(sys.argv) >= 4, f"Usage: {sys.argv[0]} <interval> {sensor} <pdu no.>"
        pdu_number = int(sys.argv[3])
        get_pdus_power(sensor, host, pdu_number)
    elif sensor == "rapl_counter":
        print(f"{sensor},host={host}", end=" ")
        get_rapl_power()
    else:
        raise ValueError("Invalid argument")


def run(sensor: str, interval: float) -> None:
    while True:
        start = time.perf_counter()
        try:
            run_one(sensor)
        except Exception as e:
            print(f'Error for sensor "{sensor}":', e, file=sys.stderr)
        duration = time.perf_counter() - start
        time.sleep(max(0, interval - duration))


def main() -> int:
    assert (
        len(sys.argv) >= 3
    ), f"Usage: {sys.argv[0]} <interval> <sensor> [sensor args...]"
    interval = float(sys.argv[1])
    sensor = sys.argv[2]
    assert sensor in ["ipmi_sensor", "pdu_sensor", "rapl_counter"], "Invalid sensor"
    try:
        run(sensor, interval)
    except KeyboardInterrupt:
        return os.EX_OK


if __name__ == "__main__":
    sys.exit(main())
