"""
status.py

Copyright 2012 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""
import time

import w3af.core.controllers.output_manager as om

from w3af.core.controllers.misc.epoch_to_string import epoch_to_string
from w3af.core.controllers.misc.number_generator import consecutive_number_generator

PAUSED = 'Paused'
STOPPED = 'Stopped'
RUNNING = 'Running'

AUDIT = 'audit'
CRAWL = 'crawl'
GREP = 'grep'

GREP_DEFAULT_ADJUSTMENT_RATIO = 2.0
AUDIT_DEFAULT_ADJUSTMENT_RATIO = 2.5
CRAWL_DEFAULT_ADJUSTMENT_RATIO = 1.75


class CoreStatus(object):
    """
    This class maintains the status of the w3afCore. During scan the different
    phases of the process will change the status (set) and the UI will be
    calling the different methods to (get) the information required.
    """

    def __init__(self, w3af_core, scans_completed=0):
        # Store the core to be able to access the queues to get status
        self._w3af_core = w3af_core

        # Init some internal values
        self._is_running = False
        self._paused = False
        self._start_time_epoch = None
        self.scans_completed = scans_completed

        # This indicates the plugin that is running right now for each
        # plugin_type
        self._running_plugin = {}
        self._latest_ptype, self._latest_pname = None, None

        # The current fuzzable request that the core is analyzing at each phase
        # where a phase means crawl/audit
        self._current_fuzzable_request = {}

        # Save the latest ETA values in order to "smooth" our ETAs
        self._eta_smooth = {AUDIT: 0,
                            GREP: 0,
                            CRAWL: 0}

    def pause(self, pause_yes_no):
        self._paused = pause_yes_no
        self._is_running = not pause_yes_no
        om.out.debug('The user paused / unpaused the scan.')

    def start(self):
        self._is_running = True
        self._start_time_epoch = time.time()

    def stop(self):
        # Now I'm definitely not running:
        self._is_running = False

    def get_status(self):
        """
        :return: A string representing the current w3af core status.
        """
        if self._paused:
            return PAUSED

        elif not self.is_running():
            return STOPPED

        else:
            crawl_plugin = self.get_running_plugin('crawl')
            audit_plugin = self.get_running_plugin('audit')

            crawl_fr = self.get_current_fuzzable_request('crawl')
            audit_fr = self.get_current_fuzzable_request('audit')

            if (crawl_plugin is None and audit_plugin is None and
                    crawl_fr is None and audit_fr is None):
                return 'Starting scan.'

            status_str = ''
            if crawl_plugin is not None and crawl_fr is not None:
                status_str += 'Crawling %s using %s.%s'
                status_str %= (crawl_fr, 'crawl', crawl_plugin)

            if audit_plugin is not None and audit_fr is not None:
                if status_str:
                    status_str += '\n'

                status_str += 'Auditing %s using %s.%s' % (audit_fr, 'audit',
                                                           audit_plugin)

            status_str = status_str.replace('\x00', '')
            return status_str

    def set_running_plugin(self, plugin_type, plugin_name, log=True):
        """
        This method saves the phase and plugin name in order to be shown
        to the user.

        :param plugin_name: The plugin_type which the w3afCore is running
        :param plugin_name: The plugin_name which the w3afCore is running
        """
        self._running_plugin[plugin_type] = plugin_name
        self._latest_ptype, self._latest_pname = plugin_type, plugin_name

    def get_running_plugin(self, plugin_type):
        """
        :return: The plugin that the core is running when the method is called.
        """
        return self._running_plugin.get(plugin_type, None)

    def latest_running_plugin(self):
        """
        :return: Tuple with plugin_type and plugin_name for the latest running
                 plugin reported using set_running_plugin.
        """
        return self._latest_ptype, self._latest_pname

    def is_running(self):
        """
        :return: If the user has called start, and then wants to know if the
        core is still working, it should call is_running() to know that.
        """
        return self._is_running

    def is_paused(self):
        return self._paused

    def get_run_time(self):
        """
        :return: The time (in minutes) between now and the call to start().
        """
        if self._start_time_epoch is None:
            raise RuntimeError('Can NOT call get_run_time before start().')

        diff = time.time() - self._start_time_epoch
        return diff / 60

    def get_run_time_seconds(self):
        """
        :return: The time (in seconds) between now and the call to start().
        """
        if self._start_time_epoch is None:
            raise RuntimeError('Can NOT call get_run_time before start().')

        return time.time() - self._start_time_epoch

    def get_scan_time(self):
        """
        :return: The scan time in a format similar to: "3h 25m 32s"
        """
        return epoch_to_string(self._start_time_epoch)

    def get_rpm(self):
        """
        :return: The number of HTTP requests per minute performed since the
                 start of the scan.
        """
        if self._start_time_epoch is None:
            raise RuntimeError('Can NOT call get_run_time before start().')

        now = time.time()
        diff = now - self._start_time_epoch
        run_time = diff / 60.0
        return int(consecutive_number_generator.get() / run_time)

    def scan_finished(self):
        self._is_running = False
        self._running_plugin = {}
        self._current_fuzzable_request = {}
        self.scans_completed += 1

    def get_current_fuzzable_request(self, plugin_type):
        """
        :return: The current fuzzable request that the w3afCore is working on.
        """
        return self._current_fuzzable_request.get(plugin_type, None)

    # pylint: disable=E0202
    def set_current_fuzzable_request(self, plugin_type, fuzzable_request):
        """
        :param fuzzable_request: The FuzzableRequest that the w3afCore is
        working on right now.
        """
        self._current_fuzzable_request[plugin_type] = fuzzable_request

    def get_crawl_input_speed(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else round_or_None(dc.in_queue.get_input_rpm())

    def get_crawl_output_speed(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else round_or_None(dc.in_queue.get_output_rpm())

    def get_crawl_qsize(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else dc.in_queue.qsize()

    def get_crawl_output_qsize(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else dc.out_queue.qsize()

    def get_crawl_processed_tasks(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else dc.out_queue.get_processed_tasks()

    def get_crawl_worker_pool_queue_size(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()
        return None if dc is None else dc.get_pool().get_inqueue().qsize()

    def has_finished_crawl(self):
        dc = self._w3af_core.strategy.get_discovery_consumer()

        # The user never enabled crawl plugins or the scan has already finished
        # and no crawl plugins will be run
        if dc is None:
            return True

        return dc.has_finished()

    def get_crawl_current_fr(self):
        return self.get_current_fuzzable_request('crawl')

    def get_crawl_eta(self, adjustment_ratio=CRAWL_DEFAULT_ADJUSTMENT_RATIO):
        return self.calculate_eta(self.get_crawl_input_speed(),
                                  self.get_crawl_output_speed(),
                                  self.get_crawl_qsize(),
                                  CRAWL,
                                  adjustment_ratio=adjustment_ratio)

    def get_grep_processed_tasks(self):
        gc = self._w3af_core.strategy.get_grep_consumer()
        return None if gc is None else gc.in_queue.get_processed_tasks()

    def get_grep_qsize(self):
        gc = self._w3af_core.strategy.get_grep_consumer()
        return None if gc is None else gc.in_queue.qsize()

    def has_finished_grep(self):
        gc = self._w3af_core.strategy.get_grep_consumer()

        # The user never enabled grep plugins or the scan has already finished
        # and no grep plugins will be run
        if gc is None:
            return True

        return gc.has_finished()

    def get_grep_input_speed(self):
        gc = self._w3af_core.strategy.get_grep_consumer()
        return None if gc is None else round_or_None(gc.in_queue.get_input_rpm())

    def get_grep_output_speed(self):
        gc = self._w3af_core.strategy.get_grep_consumer()
        return None if gc is None else round_or_None(gc.in_queue.get_output_rpm())

    def get_grep_qsize(self):
        gc = self._w3af_core.strategy.get_grep_consumer()
        return None if gc is None else gc.in_queue.qsize()

    def get_grep_eta(self, adjustment_ratio=GREP_DEFAULT_ADJUSTMENT_RATIO):
        return self.calculate_eta(self.get_grep_input_speed(),
                                  self.get_grep_output_speed(),
                                  self.get_grep_qsize(),
                                  GREP,
                                  adjustment_ratio=adjustment_ratio)

    def get_audit_input_speed(self):
        ac = self._w3af_core.strategy.get_audit_consumer()
        return None if ac is None else round_or_None(ac.in_queue.get_input_rpm())

    def get_audit_output_speed(self):
        ac = self._w3af_core.strategy.get_audit_consumer()
        return None if ac is None else round_or_None(ac.in_queue.get_output_rpm())

    def get_audit_qsize(self):
        ac = self._w3af_core.strategy.get_audit_consumer()
        return None if ac is None else ac.in_queue.qsize()

    def get_audit_processed_tasks(self):
        ac = self._w3af_core.strategy.get_audit_consumer()
        return None if ac is None else ac.in_queue.get_processed_tasks()

    def get_audit_worker_pool_queue_size(self):
        ac = self._w3af_core.strategy.get_audit_consumer()
        return None if ac is None else ac.get_pool().get_inqueue().qsize()

    def get_audit_current_fr(self):
        return self.get_current_fuzzable_request('audit')

    def has_finished_audit(self):
        ac = self._w3af_core.strategy.get_audit_consumer()

        # The user never enabled audit plugins or the scan has already finished
        # and no audit plugins will be run
        if ac is None:
            return True

        return ac.has_finished()

    def get_audit_eta(self, adjustment_ratio=AUDIT_DEFAULT_ADJUSTMENT_RATIO):
        return self.calculate_eta(self.get_audit_input_speed(),
                                  self.get_audit_output_speed(),
                                  self.get_audit_qsize(),
                                  AUDIT,
                                  adjustment_ratio=adjustment_ratio)

    def get_core_worker_pool_queue_size(self):
        return self._w3af_core.worker_pool.in_queue.qsize()

    def calculate_eta(self, input_speed, output_speed, queue_size, _type,
                      adjustment_ratio=2.0):
        """
        Do our best effort to calculate the ETA for a specific queue
        for which we have the input speed, output speed and current
        size.

        :param input_speed: The speed at which items are added to the queue
        :param output_speed: The speed at which items are read from the queue
        :param queue_size: The current queue size
        :param _type: The type of ETA we're calculating
        :param adjustment_ratio: The ratio to use to adjust the ETA when the input
                                 speed is greater than the output speed.
        :return: ETA in epoch format, None if one of the parameters is None.
        """
        if input_speed is None or output_speed is None:
            msg = ('Calculated %s ETA: None seconds. (input speed:%s,'
                   ' output speed:%s, queue size: %s, adjustment ratio: %s)')
            args = (_type,
                    input_speed,
                    output_speed,
                    queue_size,
                    adjustment_ratio)

            om.out.debug(msg % args)

            return None

        if input_speed >= output_speed:
            # This is a tricky case. The input speed is greater than
            # the output speed, which means that at this rate we will
            # never end.
            #
            # The good news is that this situation will eventually change,
            # and the output speed will be greater.
            #
            # For this case we still want to give our best guess.
            #
            # The ETA will be calculated like:
            #
            #   ETA = T(queued) + T(new) * adjustment_ratio
            #
            # Where:
            #
            #   * T(queued) is the time it will take to consume the
            #     already queued items.
            #
            #   * T(new) is the time it will take to consume the new items
            #     that will appear in the queue while we solve T(queued)
            #
            #   * `adjustment_ratio` is our way of saying: we're not sure how
            #     much time this will take, go have a coffee and come back later.
            #     This ratio changes for crawl, audit and grep queues and should
            #     be changed based on real scans. The best way to adjust these
            #     values is to run scans and use scan_log_analysis.py to check
            #     (see: show_progress_delta).
            #
            t_queued = queue_size / output_speed
            t_new = input_speed * t_queued / output_speed * adjustment_ratio
            eta_minutes = t_queued + t_new
        else:
            # This case is easier, we have an output speed which is
            # greater than the input speed, so we should be able to calculate
            # the ETA using:
            #
            #   ETA = T(queued) + T(new)
            #
            # See above to understand what those are.
            t_queued = queue_size / output_speed
            t_new = input_speed * t_queued / output_speed
            eta_minutes = t_queued + t_new

        # Smooth with average to avoid ugly spikes in the ETAs
        eta_seconds = eta_minutes * 60
        eta_seconds_avg = (eta_seconds + self._eta_smooth[_type]) / 2.0
        self._eta_smooth[_type] = eta_seconds

        msg = ('Calculated %s ETA: %.2f seconds. (input speed:%s,'
               ' output speed:%s, queue size: %s, adjustment ratio: %s)')
        args = (_type,
                eta_seconds_avg,
                input_speed,
                output_speed,
                queue_size,
                adjustment_ratio)
        om.out.debug(msg % args)

        return eta_seconds_avg

    def get_simplified_status(self):
        """
        :return: The status as a very simple string
        """
        if self.is_paused():
            return PAUSED

        elif not self.is_running():
            return STOPPED

        return RUNNING

    def epoch_eta_to_string(self, eta):
        if eta is None:
            return None

        return epoch_to_string(time.time() - eta)

    def get_status_as_dict(self):
        """
        :return: The status as a dict which I can use in JSON responses
        """

        def serialize_fuzzable_request(fuzzable_request):
            if fuzzable_request is None:
                return fuzzable_request

            return '%s %s' % (fuzzable_request.get_method(),
                              fuzzable_request.get_uri())

        crawl_fuzzable_request = self.get_current_fuzzable_request('crawl')
        crawl_fuzzable_request = serialize_fuzzable_request(crawl_fuzzable_request)

        audit_fuzzable_request = self.get_current_fuzzable_request('audit')
        audit_fuzzable_request = serialize_fuzzable_request(audit_fuzzable_request)

        eta_seconds = self.get_eta()
        eta = self.epoch_eta_to_string(eta_seconds)
        progress = self.get_progress_percentage(eta=eta_seconds)

        try:
            rpm = self.get_rpm()
        except RuntimeError:
            rpm = 0

        data = {
            'status': self.get_simplified_status(),
            'is_paused': self.is_paused(),
            'is_running': self.is_running(),

            'active_plugin':
                {'crawl': self.get_running_plugin('crawl'),
                 'audit': self.get_running_plugin('audit')},

            'current_request':
                {'crawl': crawl_fuzzable_request,
                 'audit': audit_fuzzable_request},

            'queues':
                {'crawl':
                     {
                         'input_speed': self.get_crawl_input_speed(),
                         'output_speed': self.get_crawl_output_speed(),
                         'length': self.get_crawl_qsize(),
                         'processed_tasks': self.get_crawl_processed_tasks(),
                     },
                 'audit':
                     {
                         'input_speed': self.get_audit_input_speed(),
                         'output_speed': self.get_audit_output_speed(),
                         'length': self.get_audit_qsize(),
                         'processed_tasks': self.get_audit_processed_tasks(),
                     },
                 'grep':
                     {
                         'input_speed': self.get_grep_input_speed(),
                         'output_speed': self.get_grep_output_speed(),
                         'length': self.get_grep_qsize(),
                         'processed_tasks': self.get_grep_processed_tasks(),
                     }
                },

            'eta':
                {'crawl': self.epoch_eta_to_string(self.get_crawl_eta()),
                 'audit': self.epoch_eta_to_string(self.get_audit_eta()),
                 'grep': self.epoch_eta_to_string(self.get_grep_eta()),
                 'all': eta},

            'rpm': rpm,
            'sent_request_count': self.get_sent_request_count(),
            'progress': progress,
        }

        return data

    def get_progress_percentage(self, eta=None):
        """
        :return: A % of scan progress as an integer
        """
        eta = self.get_eta() if eta is None else eta

        run_time = self.get_run_time_seconds()
        estimated_end_time = run_time + eta

        progress = int(run_time / estimated_end_time * 100)

        om.out.debug('The scan will finish in %.2f seconds (%s%% done)' % (eta, progress))

        return progress

    def get_crawl_adjustment_ratio(self):
        """
        During the first minutes of the scan the ETA calculations are usually
        very inaccurate, indicating the the scan will finish way sooner than
        reality.

        In order to fix this issue provide a set of specific adjustment
        ratios for the ETA calculation (see how these are used in calculate_eta)
        which should be used during the first minutes of the scan.

        Also provide specific adjustment ratios for different scan phases, such
        as "crawl, audit and grep running", "crawl finished, audit and grep running",
        etc.

        :return: The crawl adjustment ratio to use in this run
        """
        run_time = self.get_run_time_seconds()

        #
        # During the early phases of the scan it is easy to believe that the
        # scan will finish soon (not many items in the queue). To prevent
        # this we set a big adjustment ratio
        #
        if run_time < 30:
            return CRAWL_DEFAULT_ADJUSTMENT_RATIO * 20

        if run_time < 60:
            return CRAWL_DEFAULT_ADJUSTMENT_RATIO * 15

        if run_time < 120:
            return CRAWL_DEFAULT_ADJUSTMENT_RATIO * 7.5

        if run_time < 180:
            return CRAWL_DEFAULT_ADJUSTMENT_RATIO * 3.5

        return CRAWL_DEFAULT_ADJUSTMENT_RATIO

    def get_audit_adjustment_ratio(self):
        """
        :see: Documentation for get_crawl_adjustment_ratio
        """
        run_time = self.get_run_time_seconds()

        #
        # We know that the crawl plugin has finished, no new items will be added
        # to the audit queue. We can set audit adjustment ratio to zero
        #
        if self.has_finished_crawl():
            return 0.0

        #
        # During the early phases of the scan it is easy to believe that the
        # scan will finish soon (not many items in the queue). To prevent
        # this we set a big adjustment ratio
        #
        if run_time < 30:
            return AUDIT_DEFAULT_ADJUSTMENT_RATIO * 20.0

        if run_time < 60:
            return AUDIT_DEFAULT_ADJUSTMENT_RATIO * 10.0

        if run_time < 120:
            return AUDIT_DEFAULT_ADJUSTMENT_RATIO * 7.5

        if run_time < 180:
            return AUDIT_DEFAULT_ADJUSTMENT_RATIO * 3.5

        return AUDIT_DEFAULT_ADJUSTMENT_RATIO

    def get_grep_adjustment_ratio(self):
        """
        :see: Documentation for get_crawl_adjustment_ratio
        """
        run_time = self.get_run_time_seconds()

        #
        # When the audit and crawl plugins have finished the grep plugins need
        # to consume the queue. No more new items will be added to the queue,
        # so we can safely use an adjustment ratio of zero for the grep ETA
        # because no "uncertain amount of tasks" will be added to the queue
        #
        if self.has_finished_crawl() and self.has_finished_audit():
            return 0.0

        #
        # When both crawl and audit are running the amount of HTTP requests is
        # higher, thus it is harder to calculate the ETA.
        #
        if not self.has_finished_crawl() and not self.has_finished_audit():
            return GREP_DEFAULT_ADJUSTMENT_RATIO * 1.5

        #
        # During the early phases of the scan it is easy to believe that the
        # scan will finish soon (not many items in the queue). To prevent
        # this we set a big adjustment ratio
        #
        if run_time < 30:
            return GREP_DEFAULT_ADJUSTMENT_RATIO * 20

        if run_time < 60:
            return GREP_DEFAULT_ADJUSTMENT_RATIO * 10

        if run_time < 120:
            return GREP_DEFAULT_ADJUSTMENT_RATIO * 7.5

        if run_time < 180:
            return GREP_DEFAULT_ADJUSTMENT_RATIO * 3.5

        return GREP_DEFAULT_ADJUSTMENT_RATIO

    def log_eta(self, msg):
        om.out.debug('[get_eta] %s' % msg)

    def get_eta(self):
        """
        Calculate the estimated number of seconds to complete the scan
        :return: Scan ETA in seconds.
        """
        # We're most likely never going to reach this case, but just in case
        # I'm adding it. Just zero, meaning: we're finishing now
        if self.has_finished_grep():
            self.log_eta('ETA is 0. Grep consumer has already finished.')
            return 0

        crawl_adj = self.get_crawl_adjustment_ratio()
        audit_adj = self.get_audit_adjustment_ratio()
        grep_adj = self.get_grep_adjustment_ratio()

        # The easiest case is when we're not sending any more HTTP requests,
        # we just need to run the grep plugins (if enabled) on the HTTP requests
        # and responses that were captured before
        if self.has_finished_crawl() and self.has_finished_audit():
            self.log_eta('Crawl and audit consumers have finished,'
                         ' ETA calculated using grep ETA.')
            return self.get_grep_eta(adjustment_ratio=grep_adj)

        # The crawling phase has finished, but we're running audit (if enabled)
        # and grep (if enabled). Grep and audit plugins will run in different
        # threads. In most cases audit plugins will finish and grep plugins
        # will continue to run for (at least) a couple of minutes.
        if self.has_finished_crawl() and not self.has_finished_audit():
            grep_eta = self.get_grep_eta(adjustment_ratio=grep_adj)
            audit_eta = self.get_audit_eta(adjustment_ratio=audit_adj)

            after_audit = 0.0
            if grep_eta >= audit_eta:
                after_audit = grep_eta - audit_eta

            self.log_eta('Crawl has finished. Using audit and grep ETAs'
                         ' to calculate overall ETA.')
            return audit_eta + after_audit

        # The crawling, audit and grep (all if they were enabled) are running.
        # Estimating ETA here is difficult!
        grep_eta = self.get_grep_eta(adjustment_ratio=grep_adj)
        audit_eta = self.get_audit_eta(adjustment_ratio=audit_adj)
        crawl_eta = self.get_crawl_eta(adjustment_ratio=crawl_adj)

        after_crawl_audit = 0.0
        if grep_eta >= audit_eta:
            after_crawl_audit += grep_eta - audit_eta

        if grep_eta >= crawl_eta:
            after_crawl_audit += grep_eta - crawl_eta

        self.log_eta('Crawl, audit and grep are running.'
                     ' Using all ETAs to calculate overall ETA.')
        return crawl_eta + audit_eta + after_crawl_audit

    def get_sent_request_count(self):
        """
        :return: The number of HTTP requests that have been sent
        """
        return consecutive_number_generator.get()

    def get_long_status(self):
        if not self.is_running():
            return self.get_status()

        eta_seconds = self.get_eta()

        data = {
            'status': self.get_status(),

            'cin': self.get_crawl_input_speed(),
            'cout': self.get_crawl_output_speed(),
            'clen': self.get_crawl_qsize(),
            'ceta': self.epoch_eta_to_string(self.get_crawl_eta()),

            'ain': self.get_audit_input_speed(),
            'aout': self.get_audit_output_speed(),
            'alen': self.get_audit_qsize(),
            'aeta': self.epoch_eta_to_string(self.get_audit_eta()),

            'gin': self.get_grep_input_speed(),
            'gout': self.get_grep_output_speed(),
            'glen': self.get_grep_qsize(),
            'geta': self.epoch_eta_to_string(self.get_grep_eta()),

            'perc': self.get_progress_percentage(eta=eta_seconds),
            'eta': self.epoch_eta_to_string(eta_seconds),

            'rpm': self.get_rpm()
        }

        status_str = '%(status)s\n'

        status_str += ('Crawl phase: In (%(cin)s URLs/min)'
                       ' Out (%(cout)s URLs/min) Pending (%(clen)s URLs)'
                       ' ETA (%(ceta)s)\n')

        status_str += ('Audit phase: In (%(ain)s URLs/min)'
                       ' Out (%(aout)s URLs/min) Pending (%(alen)s URLs)'
                       ' ETA (%(aeta)s)\n')

        status_str += ('Grep phase: In (%(gin)s URLs/min)'
                       ' Out (%(gout)s URLs/min) Pending (%(glen)s URLs)'
                       ' ETA (%(geta)s)\n')

        status_str += 'Requests per minute: %(rpm)s\n\n'

        status_str += 'Overall scan progress: %(perc)s\n'
        status_str += 'Time to complete scan: %(eta)s\n'

        return status_str % data


def round_or_None(float_or_none):
    if float_or_none is None:
        return None
    else:
        return round(float_or_none, 2)
