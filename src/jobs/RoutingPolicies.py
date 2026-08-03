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
    def choose_cluster(self, job, clusters):
        if job is None or clusters is None:
            return None
        clusters = clusters.values() if type(clusters) is dict else clusters

        chosen_cluster = None
        lowest_ci_score = None

        for cluster in clusters:
                cluster_ci_score = cluster.get_weighted_carbon_intensity()
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