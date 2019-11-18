import sys
import time
import sched
import logging
import argparse
from threading import Thread
from config import seafes_config
from redis.exceptions import ConnectionError as NoMQAvailable, ResponseError, TimeoutError
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout, RequestError, TransportError

from seafes.mq import get_mq
from seafes.utils import init_logging
from seafes.utils.clear_deleted_repo_indices import clear_deleted_repo_indices
logger = logging.getLogger('seafes')


def start():
    seafes_config.load_index_master_conf()
    logger.info("Configuration file read complete.")
    try:
        indexmaster = IndexMaster()
        logger.info("Index master process initialized.")
        indexmaster.start()

        clear_task = ClearInvalidData()
        logger.info("Clear process initialized.")
        clear_task.start()
    except Exception as e:
        logger.info(e)

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


    parser_start = subparsers.add_parser('start',
                                         help='start index worker thread')
    parser_start.set_defaults(func=start)

    if len(sys.argv) == 1:
        print parser.format_help()
        return

    args = parser.parse_args()
    init_logging(args)

    args.func()


class IndexMaster(Thread):
    """ Publish the news of the events obtained from ccnet 
    """
    def __init__(self):
        Thread.__init__(self)
        self.mq = get_mq(seafes_config.subscribe_mq,
                         seafes_config.subscribe_server,
                         seafes_config.subscribe_port,
                         seafes_config.subscribe_password)

    def run(self):
        logger.info('master starting work')
        while True:
            try:
                self.master_handler()
            except Exception as e:
                logger.error('Error handing master task: %s' % e)
                #prevent waste resource if redis or others didn't connectioned
                time.sleep(0.2)

    def master_handler(self):
        p = self.mq.pubsub()
        try:
            p.subscribe('repo_update')
        except (ResponseError, NoMQAvailable, TimeoutError) as e :
            logger.error('The connection to the redis server failed: %s' % e)
        else:
            logger.info('master starting listen')
        while True:
            message = p.get_message()
            if message is not None and str(message['data']).count('\t') == 2:
                self.mq.lpush('index_task', message['data'])
                logger.info('%s has been add to task queue' % message['data'])

            if message is None:
                # prevent waste resource when no message has beend send
                time.sleep(0.5)

class ClearInvalidData(Thread):
    """ Run the next script at the next zero clock after the last script was run
    """
    def __init__(self):
        Thread.__init__(self)
        self.s = sched.scheduler(time.time, time.sleep)

    def clear(self):
        try:
            clear_deleted_repo_indices()
        except (ConnectionError, ConnectionTimeout):
            logging.warning('Elasticsearch Server Not Available')
        except RequestError as e:
            logging.warning('Request Error: %s' % e)
        except TransportError as e:
            logging.warning('Trans Error: %s' % e)
        self.run()

    def run(self):
        self.s.enter((24 - time.gmtime().tm_hour) * 60 * 60, 0, self.clear, ())
        self.s.run()


if __name__ == "__main__":
    main()
