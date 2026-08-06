import numpy as np
import os
from util import Logging

logger = Logging.get_logger()

class SubmitImmediately:
    @property
    def held_jobs(self):
        return 0
    
    def submit_job(self, job, current_time, release_target=None):
        # Immediately submit the job to the cluster
        if release_target:
            release_target.submit_job(job)
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
        self._release_counts = {
            'Deadline Forced':        0,
            'High Carbon (<75th)':    0,
            'Medium Carbon (<50th)':  0,
            'Low Carbon (<25th)':     0,
        }
        self._total_wait_hours = {
            'Deadline Forced':        0.0,
            'High Carbon (<75th)':    0.0,
            'Medium Carbon (<50th)':  0.0,
            'Low Carbon (<25th)':     0.0,
        }
        self._max_wait_seen = 0.0
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
    
    def submit_job(self, job, current_time, release_target=None):
        #Used to prevent jobs being set directly to cluster
        self._waiting_line.append({'time_arrived': current_time, 'job': job, 'release_target': release_target})

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
            reason = item['reason']
            self._release_counts[reason] += 1
            self._total_wait_hours[reason] += hours_waited
            if hours_waited > self._max_wait_seen:
                self._max_wait_seen = hours_waited
            logger.info(f"SustainableQueue releasing job {item['job'].name} "
                        f"(waited {hours_waited:.1f}h, "
                        f"reason: {item['reason']}, CI: {current_CI:.1f})")
            target = item.get('release_target') or submit_target
            target.submit_job(item['job'])
            self._released_jobs += 1

        return [item['job'] for item in release_now]

    def write_summary(self, output_dir, site_id=None):
        os.makedirs(output_dir, exist_ok=True)
        total_released = sum(self._release_counts.values())
        still_held = len(self._waiting_line)
        lines=[        
            'Temporal Shifting Summary (SustainableQueue)',
            '============================================',
            '',
            f'Site                  : {site_id or "unknown"}',
            f'CI thresholds         : low={self._low_ci:.1f}, mid={self._mid_ci:.1f}, high={self._high_ci:.1f}',
            f'Max wait (hours)      : {self._max_wait_hours}',
            f'Jobs still held at end: {still_held}',
            f'Total jobs released   : {total_released}',
            '',
            'Release breakdown:',
        ]
        for reason, count in self._release_counts.items():
            if total_released > 0:
                pct = count / total_released * 100
                avg_wait = self._total_wait_hours[reason] / count if count > 0 else 0.0
            else:
                pct = 0.0
                avg_wait = 0.0
            lines.append(f'  {reason:<30}: {count:>6} jobs ({pct:5.1f}%)  '
                        f'avg wait {avg_wait:.1f}h')

        lines += [
            '',
            f'Overall avg wait (released jobs): '
            f'{sum(self._total_wait_hours.values()) / total_released:.1f}h'
            if total_released > 0 else 'Overall avg wait: n/a',
            f'Longest wait seen     : {self._max_wait_seen:.1f}h',
        ]

        filepath = os.path.join(output_dir, 'temporal_shifting_summary.txt')
        with open(filepath, 'w') as f:
            for line in lines:
                f.write(f'{line}\n')

        for line in lines:
            logger.info(line)

class TemporalShiftingFactory:
    def create_temporal_policy(policy_name, site_id=None, carbon_intensity_data=None):
        policies = {
            "sustainable_queue": lambda: SustainableQueue(config={"site_id": site_id}, carbon_intensity_data=carbon_intensity_data),
            "submit_immediately": lambda: SubmitImmediately(),
            "none": lambda: SubmitImmediately(),  # Default to SubmitImmediately if no policy is specified
        }

        try:
            return policies[policy_name]()
        except KeyError:
            raise ValueError(f"Unknown temporal shifting policy: {policy_name}")