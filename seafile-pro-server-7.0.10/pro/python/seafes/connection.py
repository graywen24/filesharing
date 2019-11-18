import requests
from elasticsearch import Elasticsearch

from seafes.config import seafes_config

def es_get_conn():
    es = Elasticsearch(['{}:{}'.format(seafes_config.host, seafes_config.port)], maxsize=50, timeout=30)
    return es

def es_get_status():
    """ return True if es server work normal, otherwise return false
    """
    protocol = ['http', 'https']
    urls = []
    for p in protocol:
        urls.append(p + '://' + str(seafes_config.host) + ':' + str(seafes_config.port) + '/repofiles?pretty')
    alive = False
    try:
        for url in urls:
            if requests.get(url, timeout=10).status_code == 200:
                alive = True
    except:
        pass
    return alive
