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
            #logger.info(f"[{current_time}] Scheduler {site_id} has weighted carbon intensity score: {self._ci_score_store[id(scheduler)]},"
             #           f" free capacity fraction: {self._capacity_store[id(scheduler)]}")

    def choose_scheduler(self, job, schedulers):
        if job is None or schedulers is None:
            return None
        schedulers = schedulers.values() if type(schedulers) is dict else schedulers

        chosen_site = None
        lowest_ci_score = None
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
            occupancy = scheduler.cluster_occupancy()
            routing_score = ci_score * (occupancy ** self._k)
            self._ci_score_store[id(scheduler)] = ci_score
            self._routing_scores[id(scheduler)] = routing_score
            self._occupancy_store[id(scheduler)] = occupancy

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
        self._occupancy_store = {}
        self._routing_scores = {}
        self._k = k
        self._simulation_time = simulation_time 

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        for scheduler in scheduler_list:
            ci_score = scheduler.get_carbon_intensity()
            occupancy = scheduler.cluster_occupancy()
            routing_score = ci_score * (occupancy ** self._k)
            self._ci_store[id(scheduler)] = ci_score
            self._routing_scores[id(scheduler)] = routing_score
            self._occupancy_store[id(scheduler)] = occupancy

        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has carbon intensity: {self._ci_store[id(scheduler)]},"
                        f" occupancy: {self._occupancy_store[id(scheduler)]}, routing score: {self._routing_scores[id(scheduler)]}")
            
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


class OriginCapacityAwareCIRouting:
    def __init__(self, k=0.0, simulation_time=None, origin_bias=1.0):
        self._ci_store = {}
        self._occupancy_store = {}
        self._routing_scores = {}
        self._k = k
        self._simulation_time = simulation_time
        self._origin_bias = origin_bias

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        for scheduler in scheduler_list:
            ci_score = scheduler.get_carbon_intensity()
            occupancy = scheduler.cluster_occupancy()
            ci_occ_score = ci_score * (occupancy ** self._k)
            self._ci_store[id(scheduler)] = ci_score
            self._occupancy_store[id(scheduler)] = occupancy
            self._routing_scores[id(scheduler)] = ci_occ_score

        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has carbon intensity: {self._ci_store[id(scheduler)]},"
                        f" occupancy: {self._occupancy_store[id(scheduler)]}, routing score: {self._routing_scores[id(scheduler)]}")
            
    def choose_scheduler(self, job, schedulers):
        if job is None or schedulers is None:
            return None
        scheduler_list = list(schedulers.values()) if isinstance(schedulers, dict) else list(schedulers)
        if not scheduler_list:
            return None
        
        chosen_site = None
        lowest_routing_score = None
        origin_site = getattr(job, "origin_site", None)
        MAX_OCCUPANCY = 0.9

        for scheduler in scheduler_list:
            occupancy = self._occupancy_store.get(id(scheduler))
            if occupancy is not None and occupancy >= MAX_OCCUPANCY:
                continue
            self._scheduler_site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', None))
            ci_occ_score = self._routing_scores.get(id(scheduler))
            if ci_occ_score is None:
                continue
            if origin_site is not None and self._scheduler_site_id == origin_site:
                routing_score = ci_occ_score * self._origin_bias
            else:
                routing_score = ci_occ_score
            #logger.info(f"Routing score for scheduler {self._scheduler_site_id} (origin site: {origin_site}): {routing_score}")
            if lowest_routing_score is None or routing_score < lowest_routing_score:
                lowest_routing_score = routing_score
                chosen_site = scheduler
                # logger.info(f"New chosen site: {self._scheduler_site_id} with routing score: {routing_score}")
        return chosen_site
    
    
class RoutingPolicyFactory:
    def create_routing_policy(policy_name, simulation_time=None, routing_config=None):
        routing_config = routing_config or {}
        k = routing_config.get("k", 0.0)
        origin_bias = routing_config.get("origin_bias", 1.0)
        policies = {
            "origin_site": lambda: OriginSiteRouting(),
            "proportional_CI": lambda: ProportionalCIRouting(simulation_time=simulation_time),
            "proportional_capacity_aware_CI": lambda: CapacityAwareProportionalCIRouting(k=k, simulation_time=simulation_time),
            "capacity_aware_CI": lambda: CapacityAwareCIRouting(k=k, simulation_time=simulation_time),
            "origin_capacity_aware_CI": lambda: OriginCapacityAwareCIRouting(k=k, simulation_time=simulation_time, origin_bias=origin_bias),
        }

        try:
            return policies[policy_name]()
        except KeyError:
            raise ValueError(f"Invalid routing policy name: {policy_name}")
        