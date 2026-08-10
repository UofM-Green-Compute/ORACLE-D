from cluster.Cluster import Cluster
from jobs.JobScheduler import JobScheduler
from util import Logging

logger = Logging.get_logger()

class OriginSiteRouting:
    def choose_scheduler(self, job, clusters):
        if job is None or clusters is None:
            return None

        if type(clusters) is dict:
            return clusters.get(getattr(job, "origin_site", None))

        origin_site = getattr(job, "origin_site", None)
        for cluster in clusters:
            cluster_site_id = getattr(cluster, "site_id", getattr(cluster, "_site_id", None))
            if cluster_site_id == origin_site:
                return cluster
        return None

class ProportionalCIRouting:
    def __init__(self, max_capacity=0.95, simulation_time=None):
        self._ci_score_store = {}
        self._capacity_store = {}
        self._max_capacity = max_capacity
        self._simulation_time = simulation_time

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        for scheduler in scheduler_list:
            self._ci_score_store[id(scheduler)] = scheduler.get_weighted_carbon_intensity()
            self._capacity_store[id(scheduler)] = scheduler.free_capacity_fraction()
        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has weighted carbon intensity score: {self._ci_score_store[id(scheduler)]},"
                        f" free capacity fraction: {self._capacity_store[id(scheduler)]}")

    def choose_scheduler(self, job, schedulers):
        if job is None or schedulers is None:
            return None
        schedulers = schedulers.values() if type(schedulers) is dict else schedulers

        chosen_site = None
        lowest_ci_score = None
        #viable_schedulers = [scheduler for scheduler in schedulers if self._capacity_store.get(id(scheduler), 0) > self._max_capacity]
        # logger.info(f"Viable schedulers for job {getattr(job, 'job_id', 'Unknown')}: {[getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown')) for scheduler in viable_schedulers]}")
        # if not viable_schedulers:
        #     origin_site = getattr(job, "origin_site", None)
        #     logger.info(f"No viable schedulers for job "
        #                 f"{getattr(job, 'job_id', 'Unknown')}. "
        #                 f"Resorting to origin site {origin_site}.")
        #     if isinstance(schedulers, dict):
        #         return schedulers.get(origin_site)
        #     for scheduler in schedulers:
        #         cluster_site_id = getattr(scheduler,"site_id",getattr(scheduler, "_site_id", None))
        #         if cluster_site_id == origin_site:
        #             return scheduler
        #     logger.warning(f"Could not find origin site {origin_site} for job {getattr(job, 'job_id', 'Unknown')}")
        #     return None

        for scheduler in schedulers:
            site_ci_score = self._ci_score_store.get(id(scheduler))
            if lowest_ci_score is None or site_ci_score < lowest_ci_score:
                lowest_ci_score = site_ci_score
                chosen_site = scheduler

        return chosen_site

class CapacityAwareProportionalCIRouting:
    def __init__(self, k=0.0, simulation_time=None):
        self._ci_score_store = {}
        self._capacity_store = {}
        self._routing_scores = {}
        self._k = k
        self._simulation_time = simulation_time 

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        for scheduler in scheduler_list:
            ci_score = scheduler.get_weighted_carbon_intensity()
            occupancy = scheduler.get_occupancy()
            routing_score = ci_score * (occupancy ** self._k)
            self._ci_score_store[id(scheduler)] = scheduler.get_weighted_carbon_intensity()
            self._routing_scores[id(scheduler)] = routing_score

        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has weighted carbon intensity score: {self._ci_score_store[id(scheduler)]},"
                        f" occupancy: {occupancy}, routing score: {self._routing_scores[id(scheduler)]}")
            
    def choose_scheduler(self, job, schedulers):
        if job is None or schedulers is None:
            return None
        scheduler_list = list(schedulers.values()) if isinstance(schedulers, dict) else list(schedulers)
        if not scheduler_list:
            return None

        chosen_site = None
        lowest_routing_score = None

        for scheduler in scheduler_list:
            routing_score = self._routing_scores.get(id(scheduler))
            if routing_score is None:
                continue
            if lowest_routing_score is None or routing_score < lowest_routing_score:
                lowest_routing_score = routing_score
                chosen_site = scheduler
        return chosen_site

class CapacityAwareCIRouting:
    def __init__(self, k=0.0, simulation_time=None):
        self._ci_store = {}
        self._capacity_store = {}
        self._routing_scores = {}
        self._k = k
        self._simulation_time = simulation_time 

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        for scheduler in scheduler_list:
            ci_score = scheduler.get_weighted_carbon_intensity()
            occupancy = scheduler.get_occupancy()
            routing_score = ci_score * (occupancy ** self._k)
            self._ci_store[id(scheduler)] = scheduler.get_carbon_intensity()
            self._routing_scores[id(scheduler)] = routing_score

        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has carbon intensity: {self._ci_store[id(scheduler)]},"
                        f" occupancy: {occupancy}, routing score: {self._routing_scores[id(scheduler)]}")
            
    def choose_scheduler(self, job, schedulers):
        if job is None or schedulers is None:
            return None
        scheduler_list = list(schedulers.values()) if isinstance(schedulers, dict) else list(schedulers)
        if not scheduler_list:
            return None

        chosen_site = None
        lowest_routing_score = None

        for scheduler in scheduler_list:
            routing_score = self._routing_scores.get(id(scheduler))
            if routing_score is None:
                continue
            if lowest_routing_score is None or routing_score < lowest_routing_score:
                lowest_routing_score = routing_score
                chosen_site = scheduler
        return chosen_site

    
class RoutingPolicyFactory:
    def create_routing_policy(policy_name, simulation_time=None, routing_config=None):
        routing_config = routing_config or {}
        k = routing_config.get("k", 0.0)
        policies = {
            "origin_site": lambda: OriginSiteRouting(),
            "proportional_CI": lambda: ProportionalCIRouting(simulation_time=simulation_time),
            "proportional_capacity_aware_CI": lambda: CapacityAwareProportionalCIRouting(k=k, simulation_time=simulation_time),
            "capacity_aware_CI": lambda: CapacityAwareCIRouting(k=k, simulation_time=simulation_time)
        }

        try:
            return policies[policy_name]()
        except KeyError:
            raise ValueError(f"Invalid routing policy name: {policy_name}")
        