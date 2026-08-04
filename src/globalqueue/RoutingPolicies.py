from cluster.Cluster import Cluster
from util import Logging

logger = Logging.get_logger()

class OriginSiteRouting:
    def choose_cluster(self, job, clusters):
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
    def __init__(self):
        self._ci_score_store = {}

    def prepare(self, clusters):
        cluster_list = clusters.values() if isinstance(clusters,dict) else clusters
        self._ci_score_store = {id(cluster): cluster.get_weighted_carbon_intensity() for cluster in cluster_list}
        for cluster in cluster_list:
            site_id = getattr(cluster, 'site_id', getattr(cluster, '_site_id', 'Unknown'))
            logger.info(f"Cluster {site_id} has weighted carbon intensity score: {self._ci_score_store[id(cluster)]}")

    def choose_cluster(self, job, clusters):
        if job is None or clusters is None:
            return None
        clusters = clusters.values() if type(clusters) is dict else clusters

        chosen_cluster = None
        lowest_ci_score = None

        for cluster in clusters:
                cluster_ci_score = self._ci_score_store.get(id(cluster))
                if lowest_ci_score is None or cluster_ci_score < lowest_ci_score:
                    lowest_ci_score = cluster_ci_score
                    chosen_cluster = cluster

        return chosen_cluster

class RoutingPolicyFactory:
    def create_routing_policy(policy_name):
        policies = {
            "origin_site": OriginSiteRouting,  
            "proportional_CI": ProportionalCIRouting,
        }

        try:
            return policies[policy_name]()
        except KeyError:
            raise ValueError(f"Invalid routing policy name: {policy_name}")
        