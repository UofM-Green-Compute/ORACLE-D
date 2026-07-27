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
import contextlib
import sys

from simulation.Simulation import Simulation
from cluster.ClusterLoader import load_cluster_inventory
from util import Logging
import json
import os
import logging
import numpy as np
import random


logger = Logging.get_logger()



if __name__ == '__main__':
    
    run_seed = random.randint(0, 2**32 - 1)
    logger.info(f"Run seed: {run_seed}")

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


    baseline_run_dir = os.path.join(run_dir, 'baseline')
    os.makedirs(baseline_run_dir, exist_ok=True)

    baseline_config=dict(config)
    baseline_config["output"] = dict(config["output"])
    baseline_config["output"]["run_dir"] = baseline_run_dir
    baseline_config["Simulation"] = dict(config["Simulation"])
    baseline_config["Simulation"]["savings_policy"] = "none"
    baseline_config["output"]["verbosity"] = "low"

    baseline_cluster_configs = []
    for cluster_config in cluster_configs:
        baseline_cluster_config = dict(cluster_config)
        baseline_cluster_config["savings_policy"] = "none"
        baseline_cluster_configs.append(baseline_cluster_config)

    logger.info("Running baseline simulation with no carbon savings policy") 
    print(f"Running baseline simulation with no carbon savings policy")
    random.seed(run_seed)
    np.random.seed(run_seed)
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stdout(devnull):
            baseline_sim = Simulation(baseline_config, baseline_cluster_configs)
            baseline_sim.start()


    logger.info("Running actual simulation")
    print(f"Running actual simulation")
    random.seed(run_seed)
    np.random.seed(run_seed)
    sim = Simulation(config, cluster_configs)
    sim.start()

        # --- Compare actual vs baseline ---
    actual_carbon_g = sim._global_logger._total_carbon_consumed
    baseline_carbon_g = baseline_sim._global_logger._total_carbon_consumed
    carbon_saved_g = baseline_carbon_g - actual_carbon_g

    actual_duration_s = sim._final_sim_seconds
    baseline_duration_s = baseline_sim._final_sim_seconds
    time_difference_s = actual_duration_s - baseline_duration_s

    actual_energy_kwh = sim._global_logger._total_energy_consumed
    baseline_energy_kwh = baseline_sim._global_logger._total_energy_consumed
    energy_saved_kwh = baseline_energy_kwh - actual_energy_kwh

    comparison = {
        "random_seed": run_seed,
        "actual_total_carbon_g": actual_carbon_g,
        "baseline_total_carbon_g": baseline_carbon_g,
        "carbon_saved_g": carbon_saved_g,
        "carbon_saved_kg": carbon_saved_g / 1e3,
        "actual_duration_seconds": actual_duration_s,
        "baseline_duration_seconds": baseline_duration_s,
        "time_difference_seconds": time_difference_s,
        "energy_saved_kwh": energy_saved_kwh,
    }

    carbon_savings_lines = [
        f'Carbon Savings Summary',
        f'=======================',
        f'',
        f'Random seed used             : {run_seed}',
        f'',
        f'Actual total carbon consumed  : {actual_carbon_g/1e3:.3f} kg',
        f'Baseline total carbon consumed: {baseline_carbon_g/1e3:.3f} kg',
        f'Carbon saved                  : {carbon_saved_g/1e3:.3f} kg',
        f'',
        f'Actual run duration            : {actual_duration_s/3600:.2f} hours',
        f'Baseline run duration          : {baseline_duration_s/3600:.2f} hours',
        f'Time difference (actual - base): {time_difference_s/3600:.2f} hours',
        f'',
        f'Actual total energy consumed   : {actual_energy_kwh:.3f} kWh',
        f'Baseline total energy consumed: {baseline_energy_kwh:.3f} kWh',
        f'Energy saved                    : {energy_saved_kwh:.3f} kWh',
        '',
    ]
    with open(os.path.join(run_dir, 'carbon_savings_summary.txt'), 'w') as outfile:
        for line in carbon_savings_lines:
            outfile.write(f'{line}\n')

    print(f'Carbon saved vs baseline: {carbon_saved_g/1e3:.3f} kg')
    print(f'Time difference vs baseline: {time_difference_s/3600:.2f} hours')
    print(f'Energy saved vs baseline: {energy_saved_kwh:.3f} kWh')
    logger.info(f'Carbon saved vs baseline: {carbon_saved_g/1e3:.3f} kg')
    logger.info(f'Time difference vs baseline: {time_difference_s/3600:.2f} hours')
    logger.info(f'Energy saved vs baseline: {energy_saved_kwh:.3f} kWh')
    print(f'Simulation Finished. Check logs directory for output')

    sys.exit(0)
    #sim2 = Simulation('eveningclock') # Clock down the node at 5pm and up at 9pm
    #sim2.start()
