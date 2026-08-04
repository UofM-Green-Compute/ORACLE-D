# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================


import sys
import os
from datetime import datetime, timedelta

from cluster.Cluster import Cluster
from datalogger.DataLogger import DataLogger
from jobs.LocalScheduler import LocalJobScheduler
from simulation.Time import SimulationTime
from util import Logging


logger = Logging.get_logger()


class Simulation():

    def __init__(self, config, inventory, site_id, simulation_time, simulation_length, global_scheduler):

        self.site_id = site_id
        self._simulation_time = simulation_time
        self._simulation_length = simulation_length
        self._global_scheduler = global_scheduler
        # Finds the half-hour time segment to which the start of the simulation belongs and the one after the end time.
        self._simulation_starting_segment = self._simulation_time.find_hh_segment(self._simulation_time._time)
        self._simulation_maxfinal_segment = self._simulation_time.find_hh_segment(self._simulation_time._time + timedelta(seconds=self._simulation_length), 'next')
        self._jobdescript = config["output"].get("run_label", f"Simulation-{self.site_id}-{self._simulation_time.get_start_datetime().strftime('%Y%m%d-%H%M%S')}")
        self._verbosity = config["output"]["verbosity"]

        print('Setting up simulation.')
        print('Start date: ' + self._simulation_time._start_time.strftime("%d/%m/%y"))
        print('Timestep: ' + str(self._simulation_time.get_timestep()) + ' seconds')
               
        # Importing average data about the Carbon Intensity of the whole UK grid for the maxumum duration of the simulation.
        # Carbon Intensity data is in gCO2/kWh.
        if self._verbosity in ["medium", "high"]:
            logger.info('Loading in Carbon Intensity Data')
        datapath = config["carbon_intensity"]["folder"]
        datafile = config["carbon_intensity"]["filename"]
        #Convert start and end segment datetimes to format found in datafile. 
        self.datastart_str = datetime.strftime(self._simulation_starting_segment, '%Y-%m-%dT%H:%M:%S')
        self.datafinal_str = datetime.strftime(self._simulation_maxfinal_segment, '%Y-%m-%dT%H:%M:%S')
        
        linesofimport = []
        datarequired  = False
        with open(datapath+datafile) as file:
            for line in file.read().splitlines():
                line = line.split(',')

                if line[0] == self.datastart_str: # Ignores all lines before the one you want.
                    datarequired = True
                elif line[0] == self.datafinal_str: # Exit file after you have reached the end time value.
                    datarequired = False
                
                if datarequired == True: #Import data when you have found that date you want.
                    if line[1] == '': # If there is data missing
                        print("You are missing forecast CI data for the time segment: " + line[0])
                        sys.exit
                    if line[2] == '': # If there is data missing
                        print("You are missing actual CI data for the time segment: " + line[0])
                        sys.exit
                    linesofimport.append(line)    
                    
        self._CIntendata = linesofimport
        
        self.CIThresholdValue = config["carbon_intensity"]["high_CI_threshold"] #  200gCO2e/kWh - This roughly corresponds to what is labelled 'high' in the UK. For Germany I'll put this at 400

        # Create the cluster {WorkerNode[unstantiated WN of type WorkerNode]:amount[integer]}
        # Types of nodes you can currently use are {WorkerNode_h16, WorkerNode_h17, WorkerNode_d20, WorkerNode_d21, WorkerNode_d22, WorkerNode_a23},
        # the details of which can be accessed in node().system, node().cpu, and node().year.
        # You now pass the carbon data you need to estimate the amount of carbon used (manditory)
        # and a flag to set the option of how you will change the operation of the servers during runtime (none, cd1721, cdcd1721 and highforecast) (optional)

        # EXAMPLES
        # Glasgow Uni 
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_h16:13,WorkerNode_h17:43, WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36}, self._CIntendata, 'none')
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36, WorkerNode_d24:17}, self._CIntendata, 'none') # Future 1
        # self._cluster = Cluster(self._simulation_time, {WorkerNode_d20:40, WorkerNode_d21:32, WorkerNode_d22:36, WorkerNode_a24:17}, self._CIntendata, 'none') # Future 2
        # DESY
        self._cluster = Cluster(config,
                                self._simulation_time,
                                inventory,
                                self._CIntendata,
                                config["savings_policy"],
                                self.CIThresholdValue) # Starting DESY


        print('Cluster: ', end='')
        for node, cores in self._cluster._worker_node_inventory.items():
            n = node(self._simulation_time)
            print(n.hostname + ': ' + str(cores) + ' ', end='')
        print()
        print('Energy saving try: ' + self._cluster._energy_saving_try)
        print('CIThresholdValue: ' + str(self.CIThresholdValue))
        
        # Class to record statistics
        output_cfg = dict(config.get("output", {}))
        base_run_dir = output_cfg.get("run_dir") or os.path.join(os.getcwd(), "logs")
        if not os.path.isabs(base_run_dir):
            base_run_dir = os.path.join(os.getcwd(), base_run_dir)
        site_output_cfg = dict(output_cfg)
        site_output_cfg["run_dir"] = os.path.join(base_run_dir, self.site_id.lower())
        self._datalogger = DataLogger({**config, "cluster_id": self.site_id, "site_id": self.site_id, "output": site_output_cfg})
        self._cluster.set_datalogger_handlers(self._datalogger.job_submit, 
                                              self._datalogger.job_start, 
                                              self._datalogger.job_finish,
                                              self._datalogger.energy_and_carbon_consumed, 
                                              self._datalogger.peaktime_energy_and_carbon_consumed,
                                              self._datalogger.sum_occupancy )

        # Create a job scheduler to initally seed the cluster with jobs and provide jobs on a regular notice. Needs to know about this cluster
        # Format for initial jobs is a dictionary of {'VO1':jobs, 'VO2':jobs, [...]}
        # Format for regular jobs is a list  of lists of a dictionary of [[{'VO1':jobs per X seconds, 'VO2':jobs per X seconds, [...]}, X], [....] ]
        # self._jobScheduler = JobScheduler(self._simulation_time, self._cluster, {'GridPP':10} , None)

        self._jobScheduler = LocalJobScheduler(self.site_id, self._simulation_time, self._cluster)
        self._global_scheduler.register_site(self.site_id, self._jobScheduler)

        print ('Jobs: ', end='')
        for vo, jobs in self._global_scheduler.get_inital_mix(self.site_id).items():
            print(vo + ': ' + str(jobs), end='')
        regular_jobs = self._global_scheduler.get_regular_jobs(self.site_id)
        if regular_jobs:
            print(' then ', end='')
            for l1 in regular_jobs:
                vos = l1[0]
                secs = l1[1]
                for vo, jobs in vos.items():
                    print(vo + ': ' + str(jobs), end=' ')
                print(' per ' + str(secs/3600) +  ' hours', end='')
        print ()
        
        if self._verbosity in ["low", "medium", "high"]:
            simulation_parameters = self._get_simulation_parameters(datapath, datafile)
            self._datalogger.set_simulation_parameters(simulation_parameters)
            simulation_parameters_text = self._format_simulation_parameters(simulation_parameters)
            logger.info('Created simulation with parameters:\n%s', simulation_parameters_text)
            self._write_simulation_parameters(simulation_parameters_text)
        print(f'Simulation Started. Good Luck')


    def _write_simulation_parameters(self, simulation_parameters):
        run_dir = self._datalogger._run_dir
        if run_dir:
            os.makedirs(run_dir, exist_ok=True)
            with open(os.path.join(run_dir, 'parameters.txt'), 'w') as outfile:
                outfile.write(simulation_parameters)
                outfile.write('\n')


    def _get_simulation_parameters(self, carbon_data_path, carbon_data_file):
        cluster_inventory = {}
        for node, quantity in self._cluster._worker_node_inventory.items():
            worker_node = node(self._simulation_time)
            cluster_inventory[worker_node.hostname] = quantity

        regular_jobs = [
            {
                "job_mix": job_mix,
                "incoming_timestep_seconds": secs,
            }
            for job_mix, secs in self._global_scheduler.get_regular_jobs(self.site_id)
        ]

        return {
            "site_id": self.site_id,
            "start_time": str(self._simulation_time.get_start_datetime()),
            "max_end_time": str(self._simulation_time.get_start_datetime() + timedelta(seconds=self._simulation_length)),
            "simulation_length_seconds": self._simulation_length,
            "timestep_seconds": self._simulation_time.get_timestep(),
            "savings_policy": self._cluster._energy_saving_try,
            "carbon_intensity": {
                "file": f'{carbon_data_path}{carbon_data_file}',
                "segments": {
                    "start": self.datastart_str,
                    "end": self.datafinal_str,
                },
                "high_CI_threshold": self.CIThresholdValue,
            },
            "cluster": {
                "worker_nodes": self._cluster.get_number_of_nodes(),
                "worker_cores": self._cluster.get_number_of_cores(),
                "worker_node_inventory": cluster_inventory,
            },
            "jobs": {
                "initial": self._global_scheduler.get_inital_mix(self.site_id),
                "regular_incoming": regular_jobs,
            },
        }


    def _format_simulation_parameters(self, simulation_parameters):
        carbon_intensity = simulation_parameters["carbon_intensity"]
        cluster = simulation_parameters["cluster"]
        jobs = simulation_parameters["jobs"]
        regular_jobs = 'none'
        if jobs["regular_incoming"]:
            regular_jobs = ', '.join(
                f'{vo}: {count} per {regular_job["incoming_timestep_seconds"]} seconds'
                for regular_job in jobs["regular_incoming"]
                for vo, count in regular_job["job_mix"].items()
            )

        return '\n'.join([
            f'  start_time: {simulation_parameters["start_time"]}',
            f'  max_end_time: {simulation_parameters["max_end_time"]}',
            f'  simulation_length_seconds: {simulation_parameters["simulation_length_seconds"]}',
            f'  timestep_seconds: {simulation_parameters["timestep_seconds"]}',
            f'  savings_policy: {simulation_parameters["savings_policy"]}',
            f'  carbon_intensity_file: {carbon_intensity["file"]}',
            f'  carbon_intensity_segments: {carbon_intensity["segments"]["start"]} to {carbon_intensity["segments"]["end"]}',
            f'  high_CI_threshold: {carbon_intensity["high_CI_threshold"]}',
            f'  worker_nodes: {cluster["worker_nodes"]}',
            f'  worker_cores: {cluster["worker_cores"]}',
            f'  worker_node_inventory: {self._format_job_mix(cluster["worker_node_inventory"])}',
            f'  initial_jobs: {self._format_job_mix(jobs["initial"])}',
            f'  regular_incoming_jobs: {regular_jobs}',
        ])


    def _format_job_mix(self, job_mix):
        if not job_mix:
            return 'none'
        return ', '.join(f'{vo}: {jobs}' for vo, jobs in job_mix.items())

    def prepare(self):
        #runs once before shared loops starts
        #Permantly run nodes clocked down.
        if self._cluster._energy_saving_try == 'cd':
            for worker_node in self._cluster._worker_nodes:
                worker_node.clock_down()    
        if self._cluster._energy_saving_try == 'cdcd':  
            for worker_node in self._cluster._worker_nodes:
                worker_node.clock_down()
                worker_node.clock_down()

    def update(self):
        #called once per timestep by main
        self._cluster.update()

    def is_mission_accomplished(self):
        return self._cluster._mission_accomplished

    def finish(self, simtottime_seconds):
        realtottime_seconds = (datetime.now() - self._simulation_time.get_origin_datetime()).total_seconds()
        self._datalogger.print_summary(True, self._jobdescript, simtottime_seconds, self._simulation_time.get_timestep(), realtottime_seconds)                  
        if self._verbosity in ["medium", "high"]:
            logger.info(f'Site {self.site_id}: No more jobs!')
            logger.info(f'Ending {self.site_id} simulation at {self._simulation_time.get_current_datetime()}')
        print(f'{self.site_id} Simulation Finished. Check logs directory for output')