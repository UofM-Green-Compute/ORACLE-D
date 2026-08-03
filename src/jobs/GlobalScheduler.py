# SPDX-License-Identifier: Apache-2.0
# Copyright 2023-2026 Deutsches Elektronen Synchrotron DESY 
#                     and the University of Glasgow
# Authors: Dwayne Spiteri and Gordon Stewart.
# For more information about rights and fair use please refer to src/Main.py.
# For full detailed and legal infomration please read the LICENSE and NOTICE
#    files in the main directory 
# ===========================================================================

from jobs.VOJobFactory import VOJobFactory, GridPPJobFactory, ATLASJobFactory, LHCbJobFactory
from jobs.RoutingPolicies import RoutingPolicyFactory

class GlobalJobScheduler():

    def __init__(self, simulation_time, sites, cluster_configs, routing_policy= 'origin_site'):
        self._simulation_time = simulation_time
        self._sites = sites
        #self._cluster = cluster_to_submit_jobs_to
        self._routing_policy = routing_policy
        # Load in the job mixed
        self._inital_job_mix = {}
        self._regular_incoming_jobs = {}
        for  cluster_config in cluster_configs:
            site_id = cluster_config["cluster_id"]
            jobs = cluster_config["jobs"]

            self._inital_job_mix[site_id] = jobs.get("initial_jobs", {})
            if jobs.get("regular_incoming_jobs"):
                self._regular_incoming_jobs[site_id] = [jobs["regular_incoming_mix"], jobs["incoming_timestep"]]
        # Create the job factories
        self._factories = {'prod': {'ATLAS': ATLASJobFactory('ATLAS-Prod-'), 'LHCb': LHCbJobFactory('LHCb-Prod-')}, 'GridPP': {'GridPP': GridPPJobFactory('GridPP-')},
                           'hourly': {'ATLAS': ATLASJobFactory('ATLAS-Hourly-'), 'LHCb': LHCbJobFactory('LHCb-Hourly-'), 'GridPP': GridPPJobFactory('GridPP-Hourly-')}}

        self._basic_job = VOJobFactory('VO-Basic-')
        self._policy = RoutingPolicyFactory.create_routing_policy(routing_policy)
        self._site_schedulers = {}
        # Seed the cluster with initial jobs
        # Format for initial jobs is a dictionary of {'VO1':jobs, 'VO2':jobs, [...]}
        if self._inital_job_mix != None:
            for site_id, VO in self._inital_job_mix.items():
                for VO, amount in VO.items():
                    for _ in range(amount):
                        job = self._create_job(VO, 'prod')
                        job.origin_site = site_id
                        self.dispatch_job(job)

    def register_site(self, site_id, scheduler):
        self._sites[site_id] = scheduler
        self._site_schedulers[site_id] = scheduler

    def get_inital_mix(self, site_id):
        return self._inital_job_mix.get(site_id, {})

    def get_regular_jobs(self, site_id):
        regular_jobs = self._regular_incoming_jobs.get(site_id)
        if not regular_jobs:
            return []
        return [(dict(job_mix), cycle) for job_mix, cycle in [regular_jobs]]

    def _create_job(self, VO, job_type='prod'):
        factory = self._factories[job_type].get(VO, self._basic_job)
        return factory.create_job()

    def dispatch_job(self, job):
        cluster_to_submit_jobs_to = self._policy.choose_cluster(job, self._sites)
        self._sites[cluster_to_submit_jobs_to].submit_job(job)
  
        
    def update(self):
        # Jobs to be submitted while the simulation is ongoing
        # Format for regular jobs is a tuple of a dictionary of [{'VO1':jobs per X seconds, 'VO2':jobs per X seconds, [...]}, X]
        if self._regular_incoming_jobs != None:
            for list in self._regular_incoming_jobs:
                if len(list) != 2:
                    raise TypeError("The type of list in this list of lists should be a tuple of [ {VO : jobs_per_cycle}, cycle_in_sec ]")
                dict_VO_jobs_per_cycle = list[0]
                cycle = list[1]

            for cluster_to_submit_jobs_to, regular_jobs in self._regular_incoming_jobs.items():
                cluster_scheduler = self._sites[cluster_to_submit_jobs_to]
                if not cluster_scheduler.has_running_jobs() and not cluster_scheduler.has_queued_jobs():
                    continue

                for dict_VO_jobs_per_cycle, cycle in regular_jobs:
                    timediff = self._simulation_time.get_current_datetime() - self._simulation_time.get_start_datetime()
                    cyclespassed = timediff.total_seconds()/cycle
                    if cyclespassed != 0 and cyclespassed % 1 == 0:
                        for VO, amount in dict_VO_jobs_per_cycle.items():
                            for _ in range(amount):
                                job = self._create_job(VO, 'hourly')
                                job.origin_site = self._site_id
                                self.dispatch_job(job)

                # Check to see if multiples of cycle number number of seconds have gone by.

