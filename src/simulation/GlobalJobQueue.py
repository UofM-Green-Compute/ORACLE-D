from collections import defaultdict, deque
import json
import os

from util import Logging

logger = Logging.get_logger()

class GlobalJobQueue:

    _MAX_ROUTING_LOGS = 100
    def __init__(self):
        self._global_queue = deque()
        self._site_list = {}
        self._jobs_routed_logged = 0
        self._routed_counts = defaultdict(int)
        self._jobs_routed = 0

    def set_clusters(self, site_list):
        self._site_list = site_list

    def submit_job(self, job):
        self._global_queue.append(job)
        return job

    def enqueue(self, job):
        return self.submit_job(job)

    def get_jobs(self):
        return list(self._global_queue)

    def remove_job(self, job):
        try:
            self._global_queue.remove(job)
        except ValueError:
            return False
        return True

    def has_jobs(self):
        return len(self._global_queue) > 0

    def size(self):
        return len(self._global_queue)

    def choose_cluster(self,job, clusters):
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

    def get_routing_counts(self):
        return dict(self._routed_counts)

    def update(self):
        while self.has_jobs():
            job = self._global_queue.popleft()
            destination = self.choose_cluster(job, self._site_list)
            if destination is None:
                raise ValueError(f"No cluster found for job origin site {getattr(job, 'origin_site', None)}")
            origin_site = getattr(job, "origin_site", None)
            if origin_site is not None:
                self._routed_counts[origin_site] += 1
            self._jobs_routed += 1
            if self._jobs_routed_logged < self._MAX_ROUTING_LOGS:
                logger.info(f"Routed job %s (origin_site=%s) to cluster %s", job.name, getattr(job, "origin_site", None), getattr(destination, "site_id", None))
                self._jobs_routed_logged += 1
                if self._jobs_routed_logged >= self._MAX_ROUTING_LOGS:
                    logger.info("Maximum number of job routing logs reached. Further routing logs will be suppressed.")
            destination.submit_job(job)

    def write_summary(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        known_sites = list(self._site_list.keys())
        counts = self.get_routing_counts()
        summary = {"total_jobs_routed": self._jobs_routed, "known_sites": known_sites, "jobs_routed_per_site": counts}
        lines = [
            'Routing Summary',
            '================',
            '',
            f'Known sites          : {", ".join(known_sites) if known_sites else "none"}',
            f'Total jobs routed    : {self._jobs_routed}',
            '',
        ]
        for site_id in known_sites:
            lines.append(f'  {site_id}: {counts.get(site_id, 0)} jobs routed')
 
        # Flag any site that received jobs but isn't a known cluster - this
        # would indicate a routing/config problem (e.g. a typo'd origin_site).
        unknown_sites = [site for site in counts if site not in known_sites]
        if unknown_sites:
            lines.append('')
            lines.append('WARNING - jobs routed to unrecognised site IDs:')
            for site_id in unknown_sites:
                lines.append(f'  {site_id}: {counts[site_id]} jobs')
        lines.append('')
 
        with open(os.path.join(output_dir, 'routing_summary.txt'), 'w') as outfile:
            for line in lines:
                outfile.write(f'{line}\n')
 
        with open(os.path.join(output_dir, 'routing_summary.json'), 'w') as outfile:
            json.dump(summary, outfile, indent=4)
            outfile.write('\n')
 
        for line in lines:
            logger.info(line)
