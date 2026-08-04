import json
import os
from collections import defaultdict, deque
from util import Logging

logger = Logging.get_logger()

class GlobalJobQueue:

    _MAX_ROUTING_LOGS = 2000
    def __init__(self, routing_policy):
        self._global_queue = deque()
        self._site_list = {}
        self._jobs_routed_logged = 0
        self._routed_counts = defaultdict(int)
        self._jobs_routed = 0
        self._routing_policy = routing_policy

    def set_local_schedulers(self, site_list):
        self._site_list = site_list

    def submit_job(self, job):
        self._global_queue.append(job)
        return job

    def get_jobs(self):
        return list(self._global_queue)

    def has_jobs(self):
        return bool(self._global_queue)

    def get_routing_counts(self):
        return dict(self._routed_counts)

    def update(self):
        while self.has_jobs():
            job = self._global_queue.popleft()
            destination = self._routing_policy.choose_cluster(job, self._site_list)
            if destination is None:
                raise ValueError(f"No cluster returned for job {job.name} with origin_site {getattr(job, 'origin_site', None)}")
        
            self._routed_counts[job.origin_site] += 1
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
        summary = {"routing_policy": self._routing_policy.__class__.__name__, "total_jobs_routed": self._jobs_routed,
                    "known_sites": known_sites, "jobs_routed_per_site": counts}
        lines = [
            'Routing Summary',
            '================',
            '',
            f'Routing policy      : {self._routing_policy.__class__.__name__}',
            f'Known sites          : {", ".join(known_sites) if known_sites else "none"}',
            f'Total jobs routed    : {self._jobs_routed}',
            '',
        ]
        for site_id in known_sites:
            lines.append(f'  {site_id}: {counts.get(site_id, 0)} jobs routed')
 
        # Flag any site that received jobs but isn't a known cluster - this
        # would indicate a routing/config problem (e.g. a typo'd origin_site).

        with open(os.path.join(output_dir, 'routing_summary.txt'), 'w') as outfile:
            for line in lines:
                outfile.write(f'{line}\n')
 
        for line in lines:
            logger.info(line)
