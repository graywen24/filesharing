#coding: utf8
import logging

from elasticsearch.exceptions import NotFoundError
from elasticsearch.helpers import bulk as es_bulk
from elasticsearch.helpers import scan

logger = logging.getLogger('seafes')

class SeafileIndexBase(object):
    def __init__(self, es):
        """
        Base class for indices in ES. Provides some helper functions like
        create_index_if_missing() and refresh().

        :type es: elasticsearch.Elasticsearch
        """
        self.es = es

    def create_index_if_missing(self, index_settings=None):
        if not self.es.indices.exists(index=self.INDEX_NAME):
            body = {}
            if index_settings:
                body['settings'] = index_settings
            self.es.indices.create(index=self.INDEX_NAME, body=body)

            self.es.indices.put_mapping(
                index=self.INDEX_NAME,
                doc_type=self.MAPPING_TYPE,
                body=self.MAPPING
            )

            self.es.indices.refresh(index=self.INDEX_NAME)

    def refresh(self):
        self.es.indices.refresh(index=self.INDEX_NAME)

    def bulk(self, actions, **kw):
        kw.setdefault('chunk_size', 100)
        kw.setdefault('max_chunk_bytes', 5 * 1024 * 1024)
        kw.setdefault('raise_on_error', False)
        ignore_not_found = kw.pop('ignore_not_found', False)
        _, errors = es_bulk(self.es, actions, **kw)
        if errors:
            if ignore_not_found and all([e.get('delete', {}).get('status') == 404 for e in errors]):
                # This could happen, e.g. when:
                # 1. user deletes two files file2 and file2 in repo A
                # 2. ES server fails when we're updating index for repo A, file1 is deleted from index but file2 is not
                # 3. The next time when we recovery this repo, we would try to delete file1 again.
                pass
            else:
                logger.error('errors when indexing: %s', errors)
                raise Exception('errors when indexing: {}'.format(errors))
