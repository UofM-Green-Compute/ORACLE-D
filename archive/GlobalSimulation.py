#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# ========================================================================
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# The main repository houses LICENSE and NOTICE files for your infromation 
# ========================================================================

import json
import os
import sys
from datetime import datetime

from cluster.ClusterLoader import load_cluster_inventory
from datalogger.DataLogger import DataLogger
from simulation.Simulation import Simulation
from simulation.Time import SimulationTime
from util import Logging


logger = Logging.get_logger()


class GlobalSimulation():

    def __init__(self, config):
        self._config = config
        self._verbosity = config["output"]["verbosity"]
        self._simulation_length = config["Simulation"]["simulation_length"]
        self._shared_time = SimulationTime(config, config["Simulation"]["desired_starttime"])
        self._site_simulations = []
        self._run_dir = config["output"]["run_dir"]

        print('Setting up global multi-site simulation.')
        print('Start date: ' + self._shared_time._start_time.strftime("%d/%m/%y"))
        print('Timestep: ' + str(self._shared_time.get_timestep()) + ' seconds')

        for index, site_config in enumerate(config["sites"], start=1):
            runtime_config = self._build_site_config(site_config, index)
            site_run_dir = self._create_site_run_dir(runtime_config)
            runtime_config["output"]["run_dir"] = site_run_dir

            with open(os.path.join(site_run_dir, 'multiconfig.json'), 'w') as outfile:
                json.dump(runtime_config, outfile, indent=4)
                outfile.write('\n')

            inventory = load_cluster_inventory(
                runtime_config["cluster"]["inventory_csv"],
                runtime_config["cluster"]["frequency_csv"],
                cluster_name=runtime_config["cluster"]["cluster_name"],
                strict=runtime_config["cluster"]["strict"],
            )

            simulation = Simulation(
                runtime_config,
                inventory,
                simulation_time=self._shared_time,
                site_id=runtime_config["site_id"],
            )
            self._site_simulations.append(simulation)


    def _build_site_config(self, site_config, index):
        runtime_config = {
            "Simulation": dict(self._config["Simulation"]),
            "carbon_intensity": dict(site_config["carbon_intensity"]),
            "cluster": dict(site_config["cluster"]),
            "jobs": dict(site_config["jobs"]),
            "output": dict(self._config["output"]),
        }
        site_id = site_config.get("site_id", f"site_{index}")
        runtime_config["site_id"] = site_id
        runtime_config["Simulation"]["savings_policy"] = site_config.get(
            "savings_policy",
            runtime_config["Simulation"].get("savings_policy", "None"),
        )
        runtime_config["output"]["run_label"] = f'{self._config["output"].get("run_label", "simulation")}_{site_id}'
        return runtime_config


    def _create_site_run_dir(self, runtime_config):
        site_run_dir = os.path.join(self._run_dir, runtime_config["site_id"])
        os.makedirs(site_run_dir, exist_ok=True)
        return site_run_dir


    def _build_global_datalogger(self):
        global_logger = DataLogger(self._config)
        global_logger._site_id = "all_sites"

        if not self._site_simulations:
            return global_logger

        dataloggers = [simulation._datalogger for simulation in self._site_simulations]
        global_logger._jobs_submitted = sum(datalogger._jobs_submitted for datalogger in dataloggers)
        global_logger._jobs_started = sum(datalogger._jobs_started for datalogger in dataloggers)
        global_logger._jobs_finished = sum(datalogger._jobs_finished for datalogger in dataloggers)
        global_logger._jobs_failed = sum(datalogger._jobs_failed for datalogger in dataloggers)
        global_logger._jobs_aborted = sum(datalogger._jobs_aborted for datalogger in dataloggers)
        global_logger._jobs_total_cores_used = sum(datalogger._jobs_total_cores_used for datalogger in dataloggers)
        global_logger._cumulative_cpu_time = sum(datalogger._cumulative_cpu_time for datalogger in dataloggers)
        global_logger._cumulative_wallclock_time = sum(datalogger._cumulative_wallclock_time for datalogger in dataloggers)
        global_logger._total_energy_consumed = sum(datalogger._total_energy_consumed for datalogger in dataloggers)
        global_logger._peaktime_energy_consumed = sum(datalogger._peaktime_energy_consumed for datalogger in dataloggers)
        global_logger._total_carbon_consumed = sum(datalogger._total_carbon_consumed for datalogger in dataloggers)
        global_logger._peaktime_carbon_consumed = sum(datalogger._peaktime_carbon_consumed for datalogger in dataloggers)
        global_logger._sum_occupancy = sum(datalogger._sum_occupancy for datalogger in dataloggers) / len(dataloggers)
        return global_logger


    def _write_global_summary(self):
        global_logger = self._build_global_datalogger()
        sim_seconds = (self._shared_time.get_current_datetime() - self._shared_time.get_start_datetime()).total_seconds()
        real_seconds = (datetime.now() - self._shared_time.get_origin_datetime()).total_seconds()

        global_logger.print_summary(
            True,
            "all_sites",
            sim_seconds,
            self._shared_time.get_timestep(),
            real_seconds,
            summary_dir=self._run_dir,
        )
        print('Global simulation stats:')
        print(f"Number of sites: {len(self._site_simulations)}, Site IDs:", ', '.join(simulation._site_id for simulation in self._site_simulations))

    def start(self):
        while True:
            simtottime = self._shared_time.get_current_datetime() - self._shared_time.get_start_datetime()

            if simtottime.total_seconds() >= self._simulation_length:
                for simulation in self._site_simulations:
                    if not simulation._finished:
                        simulation._finalize('time_limit')
                self._write_global_summary()
                print('Global simulation finished. Check logs directory for output')
                sys.exit(0)

            all_finished = True
            for simulation in self._site_simulations:
                if not simulation._finished:
                    all_finished = False
                    simulation.step()

            if all_finished:
                self._write_global_summary()
                print('Global simulation finished. Check logs directory for output')
                sys.exit(0)

            self._shared_time.advance()