# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================

from util import Logging
import json
import os
import numpy as np

logger = Logging.get_logger()


class DataLogger():

    # This should also write to disk...

    def __init__(self, config): 
        self._jobs_submitted = 0
        self._jobs_started = 0
        self._jobs_finished = 0
        self._jobs_failed = 0
        self._jobs_aborted = 0
        self._jobs_total_cores_used = 0        

        # Could store these by job type...
        self._cumulative_cpu_time = 0
        self._cumulative_wallclock_time = 0
        self._total_energy_consumed = 0
        self._peaktime_energy_consumed = 0
        self._total_carbon_consumed = 0
        self._peaktime_carbon_consumed = 0
        self._sum_occupancy = 0
        
        # Averages
        self._avg_jobs_completed = 0
        self._avg_energy_per_job = 0
        self._avg_carbon_per_job = 0
        self._avg_occupancy = 0

        self._job_durations = []

        # verbosity
        self._verbosity = config["output"]["verbosity"]
        self._run_dir = config["output"].get("run_dir", "logs")
        self._site_id = config.get("site_id", config.get("output", {}).get("site_id", "site"))
        self._simulation_parameters = {}


    def set_simulation_parameters(self, simulation_parameters):
        self._simulation_parameters = simulation_parameters


    def job_submit(self, job):
        pass


    def job_start(self, job, worker_node):
        if self._verbosity in ["high"]:
            logger.info(f'At site {self._site_id}: Starting job {job} on node {worker_node.hostname} with origin {job.origin_site} at {job.start_time}')
        self._jobs_started += 1
        self._jobs_total_cores_used += job.cores_req


    def job_finish(self, job, worker_node):
        if self._verbosity in ["high"]:
            logger.info(f'At site {self._site_id}: Job {job} finished on node {worker_node.hostname} with origin {job.origin_site} at {job.end_time}')
        self._jobs_finished += 1
        self._cumulative_wallclock_time += job.duration
        self._job_durations.append(job.duration)
        # Yes, Sam, I know... ;-)
        self._cumulative_cpu_time += job.duration * job.cores_req

    def energy_and_carbon_consumed(self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy):
        '''
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        '''
        #logger.info(f'Cluster {cluster} consumed {cluster.instantaneous_power_consumed} W')
        self._total_energy_consumed += timestep_energy_consumed # kWh
        self._total_carbon_consumed += timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy #g/kWh

    def peaktime_energy_and_carbon_consumed(self, timestep_energy_consumed, timestep_carbon_consumed_per_unit_energy):
        '''
        This should pass power dissipated in per timestep (kWh) such that the total consumption is in kiloWatt-hours
        This should pass carbon consumed in per timestep (g/kWh) such that the total consumption is in grams/kiloWatt-hours
        '''
        self._peaktime_energy_consumed += timestep_energy_consumed # kWh
        self._peaktime_carbon_consumed += timestep_energy_consumed * timestep_carbon_consumed_per_unit_energy #g/kWh  
    
    def sum_occupancy(self, timestep_occupancy):
        '''
        This should store the sum of the occupancy every timestep (to be divided by the number of timesteps when the simulation ends)
        '''
        self._sum_occupancy += timestep_occupancy # kWh

    def print_summary(self, summary_file, additional_description, total_simulated_time, timestepinsec, total_real_time, summary_dir=None ):
        self._avg_jobs_completed = self._jobs_finished + (self._jobs_started - self._jobs_finished)/2
        self._avg_energy_per_job = self._total_energy_consumed/self._avg_jobs_completed
        self._avg_carbon_per_job = self._total_carbon_consumed/self._avg_jobs_completed
        self._avg_occupancy      = self._sum_occupancy/(total_simulated_time/timestepinsec)
        summary = self._create_summary(total_simulated_time, total_real_time)
        job_length_stats = self._create_job_length_distribution()
        summary_lines = self._format_summary_lines(total_simulated_time, total_real_time, job_length_stats)

        self._emit_summary_lines(summary_lines)
        
        if summary_file == True:
            output_dir = summary_dir or self._run_dir
            os.makedirs(output_dir, exist_ok=True)

            summary_path = os.path.join(output_dir, 'summary.txt')
            with open(summary_path, 'a') as outfile:
                for line in summary_lines:
                    outfile.write(f'{line}\n')
                outfile.write(f'\n')

            summary_json_path = os.path.join(output_dir, 'summary.json')
            with open(summary_json_path, 'w') as outfile:
                json.dump(summary, outfile, indent=4)
                outfile.write('\n')


    def _create_summary(self, total_simulated_time, total_real_time):
        return {
            "simulation_parameters": self._simulation_parameters,
            "duration": {
                "simulated_seconds": total_simulated_time,
                "simulated_hours": total_simulated_time/3600,
                "real_seconds": total_real_time,
                "real_minutes": total_real_time/60,
            },
            "jobs": {
                "started": self._jobs_started,
                "finished": self._jobs_finished,
                "average_completed": self._avg_jobs_completed,
                "total_cores_used": self._jobs_total_cores_used,
            },
            "job_lengths": self._create_job_length_distribution(),
            "cpu": {
                "total_core_seconds": self._cumulative_cpu_time,
                "total_core_hours": self._cumulative_cpu_time/3600,
                "average_core_hours": (self._cumulative_cpu_time/3600) / self._jobs_total_cores_used,
            },
            "occupancy": {
                "average_fraction": self._avg_occupancy,
                "average_percent": self._avg_occupancy*100,
            },
            "energy": {
                "total_kwh": self._total_energy_consumed,
                "peaktime_kwh": self._peaktime_energy_consumed,
                "average_per_job_wh": self._avg_energy_per_job*1e3,
            },
            "carbon": {
                "total_g": self._total_carbon_consumed,
                "total_kg": self._total_carbon_consumed/1e3,
                "peaktime_g": self._peaktime_carbon_consumed,
                "peaktime_kg": self._peaktime_carbon_consumed/1e3,
                "average_per_job_g": self._avg_carbon_per_job,
                "peaktime_percent": self._peaktime_carbon_consumed/self._total_carbon_consumed*100,
            },
        }


    def _create_job_length_distribution(self):
        if not self._job_durations:
            return {
                "count": 0,
                "statistics": None,
                "histogram": [],
            }

        durations = np.asarray(self._job_durations, dtype=float)
        stats = {
            "min_seconds": float(np.min(durations)),
            "max_seconds": float(np.max(durations)),
            "mean_seconds": float(np.mean(durations)),
            "median_seconds": float(np.median(durations)),
            "stdev_seconds": float(np.std(durations, ddof=1)) if durations.size > 1 else 0.0
           #"p25_seconds": float(np.percentile(durations, 25)),
            #"p75_seconds": float(np.percentile(durations, 75)),
            #"p90_seconds": float(np.percentile(durations, 90)),
        }

        return {
            "count": int(durations.size),
            "statistics": stats}


    def _format_summary_lines(self, total_simulated_time, total_real_time, job_length_stats):
        job_length_text = self._format_job_length_distribution(job_length_stats)
        return [
            f'Data centre: {self._site_id}',
            f'========',
            f'Summary',
            f'========',
            f'',
            f'Total Simulated-time Duration      : {total_simulated_time/3600:4.1f} hours',
            f'Total Real-time Duration           : {total_real_time/60:4.1f} minutes',
            f'',
            f'Jobs Started                       : {self._jobs_started}',
            f'Jobs Finished                      : {self._jobs_finished}',
            f'',
            f'Total CPU duration                 : {self._cumulative_cpu_time/3600:6.1f} hours',
            f'Average CPU duration               : {(self._cumulative_cpu_time/3600) / self._jobs_total_cores_used:4.2f} hours',
            f'Average Occupancy of all clusters  : {(self._avg_occupancy*100):3.1f} %',
            f'',
            f'Total energy consumed by compute   : {self._total_energy_consumed:3.2f} kWh',
            f'Peaktime (5-9pm) energy consumption: {self._peaktime_energy_consumed:3.2f} kWh',
            f'Average energy consumption per job : {self._avg_energy_per_job*1e3:3.2f} Wh',
            f'',
            f'Job length distribution',
            *job_length_text.splitlines(),
            f'',
            f'Estimated CO2e emissions           : {self._total_carbon_consumed/1e3:.3f} kg',
            f'Estimated Peaktime CO2e emissions  : {self._peaktime_carbon_consumed/1e3:.3f} kg',
            f'Average CO2e emissions per job     : {self._avg_carbon_per_job:.3f} g',
            f'Peaktime CO2e emissions percentage : {self._peaktime_carbon_consumed/self._total_carbon_consumed*100:.3f} %',
            ''
        ]


    def _emit_summary_lines(self, summary_lines):
        for line in summary_lines:
            print(line)
            logger.info(f'[{self._site_id}] {line}')


    def _format_job_length_distribution(self, job_length_stats):
        if job_length_stats["count"] == 0:
            return '  no finished jobs recorded'

        stats = job_length_stats["statistics"]
        lines = [
            f'  jobs counted        : {job_length_stats["count"]}',
            f'  min / median / max  : {stats["min_seconds"] / 60:4.1f} / {stats["median_seconds"] / 60:4.1f} / {stats["max_seconds"] / 60:4.1f} minutes',
            f'  mean / stdev        : {stats["mean_seconds"] / 60:4.1f} / {stats["stdev_seconds"] / 60:4.1f} minutes'
            # f'  p25 / p75 / p90     : {stats["p25_seconds"] / 60:4.1f} / {stats["p75_seconds"] / 60:4.1f} / {stats["p90_seconds"] / 60:4.1f} minutes'
            # f'  histogram',
        ]

        #max_count = max(bin_data["count"] for bin_data in histogram)
        #bar_width = 30
        #for bin_data in histogram:
        #    lower_minutes = bin_data["lower_seconds"] / 60
        #    upper_minutes = bin_data["upper_seconds"] / 60
        #    bar_length = int(round((bin_data["count"] / max_count) * bar_width)) if max_count else 0
        #    bar = '#' * bar_length
        #    lines.append(
        #        f'    {lower_minutes:6.1f}-{upper_minutes:6.1f} min | {bar:<30} ({bin_data["count"]})'
        #    )

        return '\n'.join(lines)
