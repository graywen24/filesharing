import redis
import logging


def get_mq(mq_type, server, port, password):
    backend = mq_type
    if backend == 'REDIS':
        rdp = redis.ConnectionPool(host=server, port=port,
                                   password=password, retry_on_timeout=True)
        mq = redis.StrictRedis(connection_pool=rdp)
        try:
            mq.ping()
        except:
            logging.error("Redis server can't be connected: host %s, port %s", 
                          server, port)
        finally:
            # python redis is a client, each operation tries to connect and retry exec
            return mq
    else:
        logging.error("Unsupported MessageQueue Type")
