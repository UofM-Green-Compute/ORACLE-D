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

from simulation.Simulation import Simulation
from simulation.Time import SimulationTime
from jobs.GlobalScheduler import GlobalJobScheduler
from cluster.ClusterLoader import load_cluster_inventory
from util import Logging
import copy
import json
import os
import logging


logger = Logging.get_logger()


def build_cluster_configs(config, config_dir=None):
    project_dir = config_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_sites = []
    for site in config.get("sites", []):
        if isinstance(site, str):
            with open(os.path.join(project_dir, site)) as site_file:
                resolved_sites.append(json.load(site_file))
        else:
            resolved_sites.append(site)

    output_cfg = copy.deepcopy(config.get("output", {}))
    simulation_cfg = copy.deepcopy(config.get("Simulation", {}))

    cluster_configs = []
    for site in resolved_sites:
        site_output_cfg = copy.deepcopy(output_cfg)
        if "output" in site:
            site_output_cfg.update(site["output"])

        site_simulation_cfg = copy.deepcopy(simulation_cfg)
        if "Simulation" in site:
            site_simulation_cfg.update(site["Simulation"])

        cluster_configs.append({
            "cluster_id": site["site_id"],
            "cluster": site["cluster"],
            "carbon_intensity": site["carbon_intensity"],
            "jobs": site["jobs"],
            "savings_policy": site.get("savings_policy", site_simulation_cfg.get("savings_policy", "none")),
            "output": site_output_cfg,
            "Simulation": site_simulation_cfg,
        })
    return cluster_configs


if __name__ == '__main__':
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(project_dir + '/configs/config.json') as f:
        config = json.load(f)

    output_cfg = config.setdefault("output", {})
    verbosity_raw = output_cfg.get("verbosity")
    config["output"]["verbosity"] = Logging.normalize_verbosity(verbosity_raw)

    config_dir = os.path.dirname(os.path.abspath(os.path.join(project_dir, 'configs/config.json')))
    cluster_configs = build_cluster_configs(config, config_dir=config_dir)
    routing_policy = config["Simulation"].get("routing",{}).get("policy", "origin_site")

    if config["output"].get("debug", False):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    run_dir = Logging.create_run_directory(config)
    with open(os.path.join(run_dir, 'config.json'), 'w') as outfile:
        json.dump(config, outfile, indent=4)
        outfile.write('\n')

    Logging.configure_logger(logger, logging_level, run_dir)
    logger.info(f'Writing run output to {run_dir}')

    if verbosity_raw != config["output"]["verbosity"]:
        logger.warning(f"Invalid verbosity value '{verbosity_raw}', defaulting to 'high'")

    simulation_time = SimulationTime(config, config["Simulation"]["desired_starttime"])
    simulation_time._timestep_seconds = config["Simulation"]["timestep"]
    simulation_length = config["Simulation"]["simulation_length"]

    global_scheduler = GlobalJobScheduler(simulation_time,sites={}, cluster_configs=cluster_configs, routing_policy=routing_policy)
    

    simulations = {}
    for cluster_config in cluster_configs:
        cluster_id = cluster_config["cluster_id"]
        inventory = load_cluster_inventory(
            cluster_config["cluster"]["inventory_csv"],
            cluster_config["cluster"]["frequency_csv"],
            cluster_name=cluster_config["cluster"]["cluster_name"],
            strict=cluster_config["cluster"]["strict"],
        )
        sim = Simulation(config=cluster_config, inventory=inventory, site_id=cluster_id, simulation_time=simulation_time,
                         simulation_length=simulation_length, global_scheduler=global_scheduler)
        simulations[cluster_id] = sim
        sim.prepare()

    while True:
        simtottime = simulation_time.get_current_datetime() - simulation_time.get_start_datetime()
        global_scheduler.update()
        for sim in simulations.values():
            sim.update()

        finished_sites = [site_id for site_id, sim in simulations.items() if sim.is_mission_accomplished()]
        length_exceeded = simtottime.total_seconds() >= simulation_length

        for site in finished_sites:
            for site, sim in simulations.items():
                if site not in finished_sites:
                    sim.finish(simtottime.total_seconds())
            break
        if len(finished_sites)==len(simulations):
            break

        simulation_time.advance()