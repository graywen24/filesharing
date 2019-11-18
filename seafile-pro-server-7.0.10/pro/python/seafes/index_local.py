import os
import sys
import time
import Queue
import logging
import argparse
import threading

from seafobj import commit_mgr, fs_mgr, block_mgr
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout, RequestError, TransportError
from config import seafes_config

from seafes.utils import init_logging
from seafes.connection import es_get_conn
from seafes.indexes import RepoStatusIndex, RepoFilesIndex
from seafes.file_index_updater import FileIndexUpdater
from seafes.repo_data import repo_data

MAX_ERRORS_ALLOWED = 1000
logger = logging.getLogger('seafes')

UPDATE_FILE_LOCK = os.path.join(os.path.dirname(__file__), 'update.lock')
lockfile = None
NO_TASKS = False


class IndexLocal(object):
    """ Independent update index.
    """
    def __init__(self, es):
        self.fileindexupdater = FileIndexUpdater(es)
        self.error_counter = 0
        self.worker_list = []

    def clear_worker(self):
        for th in self.worker_list:
            th.join()
        logger.info("All worker threads has stopped.")

    def run(self):
        time_start = time.time()
        repos_queue = Queue.Queue(0)
        for i in range(seafes_config.index_workers):
            thread_name = "worker" + str(i)
            logger.info("starting %s worker threads for indexing" 
                        % thread_name)
            t = threading.Thread(target=self.thread_task, args=(repos_queue, ), name=thread_name)
            t.start()
            self.worker_list.append(t)

        start, count = 0, 1000
        repos = {}
        while True:
            global NO_TASKS
            try:
                repo_commits = repo_data.get_repo_id_commit_id(start, count)
            except Exception as e:
                logger.error("Error: %s" % e)
                NO_TASKS = True
                self.clear_worker()
                return
            else:
                if len(repo_commits) == 0:
                    NO_TASKS = True
                    break
                for repo_id, commit_id in repo_commits:
                    repos_queue.put((repo_id, commit_id))
                    repos[repo_id] = commit_id
                start += 1000

        self.clear_worker()
        logger.info("index updated, total time %s seconds" % str(time.time() - time_start))
        try:
            self.clear_deleted_repo(repos.keys())
        except (ConnectionError, ConnectionTimeout):
            logger.warning('Elasticsearch Server Not Available')
            self.incr_error()
        except RequestError as e:
            logger.warning('Request Error: %s' % e)
            self.incr_error()
        except TransportError as e:
            logger.warning('Transport Error: %s' % e)
            self.incr_error()
        except:
            logger.exception('Delete Repo Error: %s' % repo_id)
            self.incr_error()

    def thread_task(self, repos_queue):
        while True:
            try:
                queue_data = repos_queue.get(False)
            except Queue.Empty:
                if NO_TASKS:
                    logger.debug(
                        "Queue is empty, %s worker threads stop"
                        %(threading.currentThread().getName())
                    )
                    break
                else:
                    time.sleep(2)
            else:
                repo_id = queue_data[0]
                commit_id = queue_data[1]
                try:
                    self.fileindexupdater.update_repo(repo_id, commit_id)
                except (ConnectionError, ConnectionTimeout):
                    logger.warning('Elasticsearch Server Not Available')
                    self.incr_error()
                except RequestError as e:
                    logger.warning('Request Error: %s' % e, exc_info=True)
                    self.incr_error()
                except TransportError as e:
                    logger.warning('Transport Error: %s' % e, exc_info=True)
                    self.incr_error()
                except:
                    logger.exception('Index Repo Error: %s' % repo_id, exc_info=True)
                    self.incr_error()

        logger.info(
            "%s worker updated at %s time" 
            %(threading.currentThread().getName(), 
            time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time())))
        )
        logger.info(
            "%s worker get %s error"
            %(threading.currentThread().getName(), 
            str(self.error_counter))
        )

    def clear_deleted_repo(self, repos):
        logger.info("start to clear deleted repo")
        repo_all = [e.get('id') for e in self.fileindexupdater.status_index.get_all_repos_from_index()]

        repo_deleted = set(repo_all) - set(repos)
        logger.info("%d repos need to be deleted."% len(repo_deleted))
        for repo in repo_deleted:
            self.delete_repo(repo)
            logger.info('Repo %s has been deleted from index.' % repo)
        logger.info("deleted repo has been cleared")

    def incr_error(self):
        self.error_counter += 1

    def delete_repo(self, repo_id):
        if len(repo_id) != 36:
            return
        self.fileindexupdater.status_index.delete_repo(repo_id)
        self.fileindexupdater.files_index.delete_repo(repo_id)


def start_index_local():
    if not check_concurrent_update():
        return 

    try:
        index_local = IndexLocal(es_get_conn())
    except Exception as e:
        logger.error("Index process init error: %s." % e)
        return

    logger.info("Index process initialized.")
    index_local.run()

    logger.info('\n\nIndex updated, statistic report:\n')
    logger.info('[commit read] %s', commit_mgr.read_count())
    logger.info('[dir read]    %s', fs_mgr.dir_read_count())
    logger.info('[file read]   %s', fs_mgr.file_read_count())
    logger.info('[block read]  %s', block_mgr.read_count())

def delete_indices():
    es = es_get_conn()
    for idx in (RepoStatusIndex.INDEX_NAME, RepoFilesIndex.INDEX_NAME):
        if es.indices.exists(idx):
            logger.warning('deleting index %s', idx)
            es.indices.delete(idx)

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands', description='')

    parser.add_argument(
        '--logfile',
        default=sys.stdout,
        type=argparse.FileType('a'),
        help='log file')

    parser.add_argument(
        '--loglevel',
        default='info',
        help='log level')

    # update index of filename and text/markdown file content
    parser_update = subparsers.add_parser('update', help='update seafile index')
    parser_update.set_defaults(func=start_index_local)

    # clear
    parser_clear = subparsers.add_parser('clear',
                                         help='clear all index')
    parser_clear.set_defaults(func=delete_indices)

    if len(sys.argv) == 1:
        print parser.format_help()
        return

    args = parser.parse_args()
    init_logging(args)

    logging.info('storage: using ' + commit_mgr.get_backend_name())

    logging.info('index office pdf: %s', seafes_config.index_office_pdf)

    args.func()

def do_lock(fn):
    if os.name == 'nt':
        return do_lock_win32(fn)
    else:
        return do_lock_linux(fn)

def do_lock_win32(fn):
    import ctypes
    import locale

    CreateFileW = ctypes.windll.kernel32.CreateFileW
    GENERIC_WRITE = 0x40000000
    OPEN_ALWAYS = 4

    encoding = locale.getdefaultlocale()[1]

    def lock_file(path):
        if isinstance(path, str):
            path = path.decode(encoding)
        lock_file_handle = CreateFileW (path,
                                        GENERIC_WRITE,
                                        0,
                                        None,
                                        OPEN_ALWAYS,
                                        0,
                                        None)

        return lock_file_handle

    global lockfile

    lockfile = lock_file(fn)

    return lockfile != -1

def do_lock_linux(fn):
    global lockfile
    lockfile = open(fn, 'w')
    try:
        import portalocker
        portalocker.lock(lockfile, portalocker.LOCK_NB | portalocker.LOCK_EX)
        return True
    except portalocker.LockException:
        return False

def check_concurrent_update():
    '''Use a lock file to ensure only one task can be running'''
    if not do_lock(UPDATE_FILE_LOCK):
        logger.error('another index task is running, quit now')
        return False

    return True

if __name__ == "__main__":
    main()
