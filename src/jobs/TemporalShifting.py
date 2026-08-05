import numpy as np
from util import Logging

logger = Logging.get_logger()

class SubmitImmediately:
    def submit_job(self, job, current_time):
        # Immediately submit the job to the cluster
        pass
    def update(self, current_time, current_CI, submit_target=None):
        # No jobs are held in this policy, so nothing to update
        return []

class SustainableQueue:
    def __init__(self, config, carbon_intensity_data=None):
        self._max_wait_hours = 24
        self._mid_wait_hours = 12
        self._short_wait_hours = 6
        self._waiting_line = []
        self._released_jobs = 0
        self.site_id = config.get("site_id")

        ci_values = []
        if carbon_intensity_data:
            ci_values = [float(row[1]) for row in carbon_intensity_data if row[1] !='']

        if ci_values:
            self._low_ci = float(np.percentile(ci_values, 25))
            self._mid_ci = float(np.percentile(ci_values, 50))
            self._high_ci = float(np.percentile(ci_values, 75))
            logger.info(f"Carbon Intensity thresholds set for {self.site_id}: Low={self._low_ci}, Mid={self._mid_ci}, High={self._high_ci}")
        else:
            self._low_ci = self._mid_ci = self._high_ci = None
            logger.warning(f"No valid carbon intensity data provided for {self.site_id}. Temporal shifting disabled.")

    @property
    def held_jobs(self):
        return len(self._waiting_line)
    
    def submit_job(self, job, current_time):
        #Used to prevent jobs being set directly to cluster
        self._waiting_line.append({'time_arrived': current_time, 'job': job})

    def update(self, current_time, current_CI, submit_target=None):
        release_now = []
        wait_longer = []

        for item in self._waiting_line:
            hours_waiting = (current_time - item['time_arrived']).total_seconds() / 3600.0

            if hours_waiting >= self._max_wait_hours:
                item['reason'] = 'Deadline Forced'
            elif hours_waiting >= self._mid_wait_hours and current_CI <= self._high_ci:
                item['reason'] = 'High Carbon (<75th)'
            elif hours_waiting >= self._short_wait_hours and current_CI <= self._mid_ci:
                item['reason'] = 'Medium Carbon (<50th)'
            elif current_CI <= self._low_ci:
                item['reason'] = 'Low Carbon (<25th)'
            else:
                wait_longer.append(item)
                continue
            release_now.append(item)

        self._waiting_line = wait_longer

        for item in release_now:
            hours_waited = (current_time - item['time_arrived']).total_seconds() / 3600.0
            logger.info(f"SustainableQueue releasing job {item['job'].name} "
                        f"(waited {hours_waited:.1f}h, "
                        f"reason: {item['reason']}, CI: {current_CI:.1f})")
            submit_target.submit_job(item['job'])
            self._released_jobs += 1

        return [item['job'] for item in release_now]

