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
    def __init__(self, simulation_time=None):
        self._ci_score_store = {}
        self._simulation_time = simulation_time

    def prepare(self, schedulers):
        scheduler_list = schedulers.values() if isinstance(schedulers,dict) else schedulers
        self._ci_score_store = {
            id(scheduler): scheduler.get_weighted_carbon_intensity()
            for scheduler in scheduler_list
        }
        for scheduler in scheduler_list:
            site_id = getattr(scheduler, 'site_id', getattr(scheduler, '_site_id', 'Unknown'))
            current_time = self._simulation_time.get_current_datetime()  # <-- add this
            logger.info(f"[{current_time}] Scheduler {site_id} has weighted carbon intensity score: {self._ci_score_store[id(scheduler)]}")

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

class RoutingPolicyFactory:
    def create_routing_policy(policy_name, simulation_time=None):
        policies = {
            "origin_site": lambda: OriginSiteRouting(),
            "proportional_CI": lambda: ProportionalCIRouting(simulation_time=simulation_time),
        }

        try:
            return policies[policy_name]()
        except KeyError:
            raise ValueError(f"Invalid routing policy name: {policy_name}")
        