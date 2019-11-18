import os
import sys
import time
import logging
import argparse
import threading
import signal

from redis.exceptions import ConnectionError as NoMQAvailable, ResponseError, TimeoutError
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout, RequestError, TransportError

from config import seafes_config
from seafes.connection import es_get_conn, es_get_status
from seafes.file_index_updater import FileIndexUpdater
from seafes.utils import init_logging
from seafes.repo_data import repo_data
from seafes.mq import get_mq

MAX_ERRORS_ALLOWED = 1000
logger = logging.getLogger('seafes')
locked_keys = set()  # record the repos which are updating by worker threads
should_stop = threading.Event()

class RefreshLockDaemon(object):
    def __init__(self):
        self.REFRESH_INTERVAL = 600  # 10 minutes

    @property
    def tname(self):
        return threading.current_thread().name

    def start(self):
        t = threading.Thread(target=self.refresh_lock, name='daemon_thread')
        t.daemon = True
        t.start()

    def refresh_lock(self):
        mq = get_mq(seafes_config.subscribe_mq,
                    seafes_config.subscribe_server,
                    seafes_config.subscribe_port,
                    seafes_config.subscribe_password)
        logger.info('%s Starting refresh locks' % self.tname)
        while True:
            try:
                # workaround for the RuntimeError: Set changed size during iteration
                copy = locked_keys.copy()

                for lock in copy:
                    ttl = mq.ttl(lock)
                    new_ttl = ttl + self.REFRESH_INTERVAL
                    mq.expire(lock, new_ttl)
                    logger.debug('%s Refresh lock [%s] timeout from %s to %s' %
                                 (self.tname, lock, ttl, new_ttl))

                time.sleep(self.REFRESH_INTERVAL)
            except Exception as e:
                logger.error(e)
                time.sleep(1)

class IndexWorker(object):
    """ The handler for redis message queue
    """
    def __init__(self, es, should_stop):
        self.FileIndexUpdater = FileIndexUpdater(es)
        self.should_stop = should_stop
        self.LOCK_TIMEOUT = 1800  # 30 minutes

    def _get_lock_key(self, repo_id):
        """Return lock key in redis.
        """
        return 'v1_' + repo_id

    def start(self):
        for i in range(seafes_config.index_slave_workers):
            threading.Thread(target=self.worker_handler, name='subscribe_' + str(i),
                             args=(self.should_stop, )).start()

    def worker_handler(self, should_stop):
        mq = get_mq(seafes_config.subscribe_mq,
                    seafes_config.subscribe_server,
                    seafes_config.subscribe_port,
                    seafes_config.subscribe_password)
        logger.info('%s starting work' % threading.current_thread().name)
        try:
            while not should_stop.isSet():
                try:
                    res = mq.brpop('index_task', timeout=30)
                    if res is not None:
                        key, value = res
                        msg = value.split('\t')
                        if len(msg) != 3:
                            logger.info('Bad message: %s' % str(msg))
                        else:
                            repo_id, commit_id = msg[1], msg[2]
                            self.worker_task_handler(mq, repo_id, commit_id,
                                                     should_stop)
                except (ResponseError, NoMQAvailable, TimeoutError) as e:
                    logger.error('The connection to the redis server failed: %s' % e)
        except Exception as e:
            logger.error('%s Handle Worker Task Error' % threading.current_thread().name)
            logger.error(e, exc_info=True)
            # prevent case that redis break at program runing.
            time.sleep(0.3)

    def worker_task_handler(self, mq, repo_id, commit_id, should_stop):
        # Python cannot kill threads, so stop it generate more locked key.
        if not should_stop.isSet():
            # set key-value if does not exist which will expire 30 minutes later
            if mq.set(self._get_lock_key(repo_id), time.time(),
                      ex=self.LOCK_TIMEOUT, nx=True):
                # get lock
                logger.info('%s start updating repo %s' %
                            (threading.currentThread().getName(), repo_id))
                self.update_repo(mq, repo_id)
            else:
                # the repo is updated by other thread, push back to the queue
                self.add_to_undo_task(mq, repo_id, commit_id)

    def update_repo(self, mq, repo_id):
        lock_key = self._get_lock_key(repo_id)
        locked_keys.add(lock_key)
        try:
            commit_id = repo_data.get_repo_head_commit(repo_id)
            if not commit_id:
                # invalid repo without head commit id
                logger.error("invalid repo : %s " % repo_id)
                return
            self.FileIndexUpdater.update_repo(repo_id, commit_id)
        except Exception as e:
            self.handle_exception(mq, repo_id, commit_id, e)
        finally:
            try:
                locked_keys.remove(lock_key)
            except KeyError:
                logger.error("%s is already removed. SHOULD NOT HAPPEN!" % lock_key)
            mq.delete(lock_key)
            logger.info("%s Finish updating repo: %s, delete redis lock %s" %
                        (threading.current_thread().name, repo_id, lock_key))

    def add_to_undo_task(self, mq, repo_id, commit_id):
        """Push task back to the end of the queue.
        """
        mq.lpush('index_task', '\t'.join(['repo-update', repo_id, commit_id]))
        logger.debug('%s push back task (%s, %s) to the queue' %
                     (threading.current_thread().name, repo_id, commit_id))

        # avoid get the same task repeatly
        time.sleep(0.5)

    def handle_exception(self, mq, repo_id, commit_id, e):
        """ if es server unreachable, process will wait until es server work normal,
            otherwise will record log then skip this task.
        """
        if isinstance(e, ConnectionError) or isinstance(e, ConnectionTimeout):
            logger.warning('elasticsearch server not available')
            self.wait_es_alive()
            self.add_to_undo_task(mq, repo_id, commit_id)
        elif isinstance(e, RequestError):
            logger.warning('Request Error: %s' % e)
        elif isinstance(e, TransportError):
            logger.warning('Transport Error: %s' % e)
        else:
            logger.exception('Index Repo %s Commit %s Error' % (repo_id, commit_id))
            logger.exception(e)

    def wait_es_alive(self):
        count = 0
        logger.warning('%s try reconnecting to elasticsearch server.' % threading.current_thread().name)
        while True:
            if es_get_status():
                logger.warning('Elasticsearch server reconnected successfully.')
                return
            else:
                time.sleep(2)
                count += 1
                if count > 100:
                    logger.info('still can not be connected')
                    count = 0

def clear(should_stop):
    seafes_config.load_index_slave_conf()
    global locked_keys
    mq = get_mq(seafes_config.subscribe_mq,
                          seafes_config.subscribe_server,
                          seafes_config.subscribe_port,
                          seafes_config.subscribe_password)
    # stop work thread
    logger.info("stop work thread")
    should_stop.set()
    # if a thread just lock key, wait to add the lock to the list.
    time.sleep(1)
    # del redis locked key
    for key in locked_keys:
        mq.delete(key)
        logger.info("redis lock key %s has been deleted" % key)
    # sys.exit
    logger.info("Exit the process")
    os._exit(0)

def signal_term_handler(signal, frame):
    logger.info("Began to clean up")
    clear(should_stop)

def set_signal():
    # TODO: look like python will add signal to queue when cpu exec c extension code,
    # and will call signal callback method after cpu exec python code
    # ref: https://docs.python.org/2/library/signal.html
    signal.signal(signal.SIGTERM, signal_term_handler)

def start():
    seafes_config.load_index_slave_conf()
    logger.info("Configuration file read complete.")
    set_signal()

    RefreshLockDaemon().start()

    try:
        indexworker = IndexWorker(es_get_conn(), should_stop)
        logger.info("Index worker process initialized.")
        indexworker.start()
    except Exception as e:
        logger.error(e)
        clear(should_stop)
    while True:
        # if main thread has been quit or join for subthread. 
        # signal callback will never be  call.
        time.sleep(2)

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands', description='')

    parser.add_argument(
        '--logfile',
        default=sys.stdout,
        type=argparse.FileType('a'),
        help='log file'
    )

    parser.add_argument(
        '--loglevel',
        default='info',
        help='log level'
    )

    parser_start = subparsers.add_parser('start',
                                         help='start index worker thread')
    parser_start.set_defaults(func=start)

    if len(sys.argv) == 1:
        print parser.format_help()
        return

    args = parser.parse_args()
    init_logging(args)

    args.func()

if __name__ == "__main__":
    main()
