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

#NEED TO EDIT MAIN TO ACCOUNT FOR NEW CONFIG STRUCTURE
from simulation.Simulation import Simulation
from simulation.GlobalSimulation import GlobalSimulation
from cluster.ClusterLoader import load_cluster_inventory
from util import Logging
import json
import os
import logging


logger = Logging.get_logger()

if __name__ == '__main__':
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(project_dir + '/configs/config.json') as f:
        config = json.load(f)

    output_cfg = config.setdefault("output", {})
    verbosity_raw = output_cfg.get("verbosity")
    config["output"]["verbosity"] = Logging.normalize_verbosity(verbosity_raw)

    if config["output"].get("debug", False):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    run_dir = Logging.create_run_directory(config)
    with open(os.path.join(run_dir, 'multi_site_config.json'), 'w') as outfile:
        json.dump(config, outfile, indent=4)
        outfile.write('\n')

    Logging.configure_logger(logger, logging_level, run_dir)
    logger.info(f'Writing run output to {run_dir}')

    if verbosity_raw != config["output"]["verbosity"]:
        logger.warning(f"Invalid verbosity value '{verbosity_raw}', defaulting to 'high'")


    config_dir = os.path.dirname(os.path.abspath(os.path.join(project_dir, 'configs/config.json')))
    resolved_sites = []
    for site_path in config["sites"]:
        with open(os.path.join(config_dir, site_path)) as site_file:
            resolved_sites.append(json.load(site_file))
    config["sites"] = resolved_sites
 
    # Reshape each site into the per-cluster config dict Simulation expects.
    cluster_configs = []
    for site in config["sites"]:
        cluster_configs.append({
            "cluster_id": site["site_id"],
            "cluster": site["cluster"],
            "carbon_intensity": site["carbon_intensity"],
            "jobs": site["jobs"],
            "savings_policy": site.get("savings_policy", config["Simulation"].get("savings_policy", "none")),
        })
 
    sim = Simulation(config, cluster_configs)
    sim.start()
    #sim2 = Simulation('eveningclock') # Clock down the node at 5pm and up at 9pm
    #sim2.start()
