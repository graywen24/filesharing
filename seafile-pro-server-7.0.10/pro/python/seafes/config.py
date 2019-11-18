#coding: UTF-8

import os
import ConfigParser
import logging

logger = logging.getLogger('seafes')

SUPPORTED_LANGS = (
    "arabic",
    "armenian",
    "basque",
    "brazilian",
    "bulgarian",
    "catalan",
    "chinese",
    "cjk",
    "czech",
    "danish",
    "dutch",
    "english",
    "finnish",
    "french",
    "galician",
    "german",
    "greek",
    "hindi",
    "hungarian",
    "indonesian",
    "italian",
    "norwegian",
    "persian",
    "portuguese",
    "romanian",
    "russian",
    "spanish",
    "swedish",
    "turkish",
    "thai"
)



class SeafesConfig(object):
    def __init__(self):
        if 'SEAFILE_CENTRAL_CONF_DIR' in os.environ:
            confdir = os.environ['SEAFILE_CENTRAL_CONF_DIR']
        else:
            confdir = os.environ['SEAFILE_CONF_DIR']
        self.seafile_conf = os.path.join(confdir, 'seafile.conf')
        self.seafile_dir = os.environ['SEAFILE_CONF_DIR']

        self.host = '127.0.0.1'
        self.port = 9200
        self.index_office_pdf = False
        self.text_size_limit = 100 * 1024 # 100 KB
        self.debug = False
        self.lang = ''

        events_conf = os.environ.get('EVENTS_CONFIG_FILE', None)
        if not events_conf:
            raise Exception('EVENTS_CONFIG_FILE not set in os.environ')

        self.load_seafevents_conf(events_conf)

    def print_config(self):
        logger.info('index text of office and pdf files: %s',
                    'yes' if self.index_office_pdf else 'no')

    def config_get_boolean(self, config, item, key):
        try:
            return config.getboolean(item, key)
        except ConfigParser.NoOptionError:
            return False
        except ConfigParser.NoSectionError:
            return False

    def config_get_string(self, config, item, key):
        try:
            return config.get(item, key)
        except ConfigParser.NoOptionError:
            return ''
        except ConfigParser.NoSectionError:
            return ''

    def config_get_int(self, config, item, key):
        try:
            return config.getint(item, key)
        except ConfigParser.NoOptionError:
            return 0
        except ConfigParser.NoSectionError:
            return 0

    def load_seafevents_conf(self, events_conf):
        defaults = {
            'index_office_pdf': 'false',
            'external_es_server': 'false',
            'es_host': '127.0.0.1',
            'es_port': '9200',
            'debug': 'false',
            'lang': '',
            'office_file_size_limit': '10', # 10 MB
            'index_workers': '2',
            'content_extract_time': '5',
            'highlight': 'plain'
        }

        cp = ConfigParser.ConfigParser(defaults)
        cp.read(events_conf)

        section_name = 'INDEX FILES'

        index_office_pdf = cp.getboolean(section_name, 'index_office_pdf')

        external_es_server = cp.getboolean(section_name, 'external_es_server')
        host = '127.0.0.1'
        port = 9200
        if external_es_server:
            host = cp.get(section_name, 'es_host')
            port = cp.getint(section_name, 'es_port')
            if port == 9500:
                # Seafile pro server earlier than 6.1.0 uses elasticsearch
                # thrift api. In Seafile Pro 6.1.0 we upgrade ES to 2.x, which
                # no longer supports thirft, thus we have to use elasticsearch
                # http api.
                port = 9200

        lang = cp.get(section_name, 'lang').lower()

        if lang:
            if lang not in SUPPORTED_LANGS:
                logger.warning('[seafes] invalid language ' + lang)
                lang = ''
            else:
                logger.info('[seafes] use language ' + lang)

        index_workers = cp.getint(section_name, 'index_workers')
        content_extract_time = cp.getint(section_name, 'content_extract_time')

        if index_workers <= 0:
            logger.warning("index workers can't less than zero.")
            index_workers = 2

        if content_extract_time <= 0:
            logger.warning("content extract time can't less than zero.")
            content_extract_time = 5

        self.index_office_pdf = index_office_pdf
        self.host = host
        self.port = port
        self.office_file_size_limit = cp.getint(section_name, 'office_file_size_limit') * 1024 * 1024

        self.debug = cp.getboolean(section_name, 'debug')
        self.lang = lang
        self.index_workers = index_workers
        self.content_extract_time = content_extract_time
        self.highlight = 'plain'

        config_highlight = cp.get(section_name, 'highlight')
        if config_highlight in ['plain', 'fvh']:
            self.highlight = config_highlight
            logger.info('[seafes] use highlighter ' +  config_highlight)
        else:
            logger.warning('[seafes] invalid highlighter ' +  config_highlight)

    def load_conf_with_environ(self, environ_name):
        events_conf = os.environ.get(environ_name, None)
        if not events_conf:
            raise Exception('%s not set in os.environ' % environ_name)
        cp = ConfigParser.ConfigParser()
        cp.read(events_conf)
        return cp


    def load_index_master_conf(self):
        cp = self.load_conf_with_environ('INDEX_MASTER_CONFIG_FILE')

        self.subscribe_mq = self.config_get_string(cp, 'DEFAULT', 'mq_type').upper()
        if self.subscribe_mq != 'REDIS':
            raise RuntimeError("Unknown database backend: %s" % self.subscribe_mq)

        self.subscribe_server = self.config_get_string(cp, self.subscribe_mq, 'server')
        self.subscribe_port = self.config_get_string(cp, self.subscribe_mq, 'port')
        self.subscribe_password = self.config_get_string(cp, self.subscribe_mq, 'password')

        if not self.subscribe_server or not self.subscribe_port:
            raise RuntimeError("Server address and port can't be empty.")


    def load_index_slave_conf(self):
        cp = self.load_conf_with_environ('INDEX_SLAVE_CONFIG_FILE')

        self.subscribe_mq = self.config_get_string(cp, 'DEFAULT', 'mq_type').upper()
        if self.subscribe_mq != 'REDIS':
            raise RuntimeError("Unknown database backend: %s" % self.subscribe_mq)

        index_slave_workers = self.config_get_int(cp, 'DEFAULT', 'index_workers')
        if index_slave_workers <= 0:
            logger.warning("index workers can't less than zero.")
            index_slave_workers = 2
        self.index_slave_workers = index_slave_workers 
        self.subscribe_server = self.config_get_string(cp, self.subscribe_mq, 'server')
        self.subscribe_port = self.config_get_string(cp, self.subscribe_mq, 'port')
        self.subscribe_password = self.config_get_string(cp, self.subscribe_mq, 'password')

        if not self.subscribe_server or not self.subscribe_port:
            raise RuntimeError("Server address and port can't be empty.")


seafes_config = SeafesConfig()
