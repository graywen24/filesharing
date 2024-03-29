# -*- coding: utf-8 -*-
import os
import logging

from ccnet.async import Timer
from seafevents.utils import get_python_executable, run


__all__ = [
    'FileUpdatesSender',
]


class FileUpdatesSender(object):

    def __init__(self):
        self._interval = 60
        self._seahub_dir = None
        self._logfile = None
        self._timer = None

        self._prepare_seahub_dir()
        self._prepare_logfile()

    def _prepare_seahub_dir(self):
        seahub_dir = os.environ.get('SEAHUB_DIR', '')

        if not seahub_dir:
            logging.critical('seahub_dir is not set')
            raise RuntimeError('seahub_dir is not set')
        if not os.path.exists(seahub_dir):
            logging.critical('seahub_dir %s does not exist' % seahub_dir)
            raise RuntimeError('seahub_dir does not exist')

        self._seahub_dir = seahub_dir

    def _prepare_logfile(self):
        log_dir = os.path.join(os.environ.get('SEAFEVENTS_LOG_DIR', ''))
        self._logfile = os.path.join(log_dir, 'file_updates_sender.log')

    def start(self, ev_base):
        logging.info('Start file updates sender, interval = %s sec', self._interval)

        self._timer = FileUpdatesSenderTimer(
            ev_base, self._interval, self._seahub_dir, self._logfile
        )


class FileUpdatesSenderTimer(Timer):

    def __init__(self, ev_base, timeout, seahub_dir, logfile):
        Timer.__init__(self, ev_base, timeout)
        self._seahub_dir = seahub_dir
        self._logfile = logfile

    def callback(self):
        self.send_file_updates()

    def send_file_updates(self):
        """send user file updates
        """

        try:
            self._send_file_updates()
        except Exception as e:
            logging.exception(e)

    def _send_file_updates(self):
        python_exec = get_python_executable()
        manage_py = os.path.join(self._seahub_dir, 'manage.py')

        cmd = [
            python_exec,
            manage_py,
            'send_file_updates',
        ]

        with open(self._logfile, 'a') as fp:
            run(cmd, cwd=self._seahub_dir, output=fp)
