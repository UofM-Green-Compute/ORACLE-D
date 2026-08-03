# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================

#from jobs.VOJobFactory import VOJobFactory, GridPPJobFactory, ATLASJobFactory, LHCbJobFactory

class LocalJobScheduler():

    def __init__(self, site_id, simulation_time, cluster_to_submit_jobs_to, inital_job_mix={'ATLAS':10,'LHCb':5}, regular_incoming_jobs=[[{'ATLAS':1,'LHCb':2},3600]]):
        self.site_id = site_id
        self._simulation_time = simulation_time
        self._cluster = cluster_to_submit_jobs_to
        
    def submit_job(self, job):
        self._cluster.submit_job(job)

    def has_running_jobs(self):
        return self._cluster.has_running_jobs()

    def has_queued_jobs(self):
        return self._cluster.has_queued_jobs()

    def current_carbon_intensity(self):
        return self._cluster.get_current_carbon_intensity()

    # def update(self):
    #     # Jobs to be submitted while the simulation is ongoing
    #     # Format for regular jobs is a tuple of a dictionary of [{'VO1':jobs per X seconds, 'VO2':jobs per X seconds, [...]}, X]
    #     if self._regular_incoming_jobs != None:
    #         for list in self._regular_incoming_jobs:
    #             if len(list) != 2:
    #                 raise TypeError("The type of list in this list of lists should be a tuple of [ {VO : jobs_per_cycle}, cycle_in_sec ]")

    #             dict_VO_jobs_per_cycle = list[0]
    #             cycle = list[1]
    #             # Check to see if multiples of cycle number number of seconds have gone by.
    #             timediff = self._simulation_time.get_current_datetime() - self._simulation_time.get_start_datetime()
    #             cyclespassed = timediff.total_seconds()/cycle
                
    #             if not self._cluster.has_running_jobs() and not self._cluster.has_queued_jobs():
    #                 continue

    #             if cyclespassed != 0 and cyclespassed % 1 == 0:
    #                 for VO, amount in dict_VO_jobs_per_cycle.items():
    #                     if VO == 'ATLAS':
    #                         for _ in range(amount):
    #                             self._cluster.submit_job(self._atlas_hourly.create_job())
    #                     elif VO == 'LHCb':
    #                         for _ in range(amount):
    #                             self._cluster.submit_job(self._lhcb_hourly.create_job())
    #                     elif VO == 'GridPP':
    #                         for _ in range(amount):
    #                             self._cluster.submit_job(self._gridpp_hourly.create_job())                                 
    #                     else:
    #                         for _ in range(amount):
    #                             self._cluster.submit_job(self._basic_job.create_job())    
