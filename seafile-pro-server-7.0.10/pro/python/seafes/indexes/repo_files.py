# coding: UTF-8

import os
import logging
from operator import or_

from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Q, Search

from .base import SeafileIndexBase

from ..utils import utf8_decode
from ..extract import get_file_suffix, ExtractorFactory
from ..config import seafes_config

from ..repo_data import repo_data

logger = logging.getLogger('seafes')

class RepoFilesIndex(SeafileIndexBase):
    INDEX_NAME = 'repofiles'
    MAPPING_TYPE = 'file'
    MAPPING = {
        '_source': {
            'enabled': True
        },
        'properties': {
            'repo': {
                'type': 'keyword',
                'index': True,
            },
            'path': {
                'type': 'keyword',
                'index': True,
            },
            'filename': {
                'type': 'text',
                'index': 'analyzed',
                'fields': {
                    'ngram': {
                        'type': 'text',
                        'index': 'analyzed',
                        'analyzer': 'seafile_file_name_ngram_analyzer',
                    },
                },
            },
            'suffix': {
                'type': 'keyword',
                'index': True,
            },
            'content': {
                'type': 'text',
                'index': 'analyzed',
                'term_vector': 'with_positions_offsets'
            },
            'is_dir': {
                'type': 'boolean',
                'index': 'not_analyzed',
            },
            'mtime': {
                'type': 'date',
            },
            'size': {
                'type': 'long'
            }
        },
    }

    index_settings = {
        'analysis': {
            'analyzer': {
                'seafile_file_name_ngram_analyzer': {
                    'type': 'custom',
                    'tokenizer': 'seafile_file_name_ngram_tokenizer',
                    'filter': [
                        'lowercase',
                    ],
                }
            },
            'tokenizer': {
                'seafile_file_name_ngram_tokenizer': {
                    'type': 'nGram',
                    'min_gram': '3',
                    'max_gram': '4',
                    'token_chars': ['letter', 'digit'],
                }
            }
        }
    }

    def __init__(self, es):
        """
        Init function.

        :type es: elasticsearch.Elasticsearch
        """
        super(RepoFilesIndex, self).__init__(es)
        self.language_index_optimization()
        self.create_index_if_missing(index_settings=self.index_settings)

    def language_index_optimization(self):
        if seafes_config.lang:
            # Use ngram for europe languages
            if seafes_config.lang != 'chinese':
                self.MAPPING['properties']['filename']['analyzer'] = seafes_config.lang
                self.MAPPING['properties']['content']['analyzer'] = seafes_config.lang
            else:
                # For chinese we don't need the ngram analyzer for file name.
                self.MAPPING['properties']['filename'].pop('fields', None)
                self.index_settings = {}

                # Use the ik_smart analyzer to do coarse-grained chinese
                # tokenization for search keywords.
                self.MAPPING['properties']['filename']['analyzer'] = 'ik_max_word'
                self.MAPPING['properties']['filename']['search_analyzer'] = 'ik_max_word'
                self.MAPPING['properties']['content']['analyzer'] = 'ik_smart'
                self.MAPPING['properties']['content']['search_analyzer'] = 'ik_smart'

    def is_chinese(self):
        return seafes_config.lang == 'chinese'

    def add_files(self, repo_id, version, files):
        '''Index newly added files. For text files, also index their content.'''
        for path, obj_id, mtime, size in files:
            self.add_file_to_index(repo_id, version, path, obj_id, mtime, size)

    def add_dirs(self, repo_id, version, dirs):
        """Index newly added dirs.
        """
        for path, obj_id, mtime, size in dirs:
            self.add_dir_to_index(repo_id, version, path, obj_id, mtime, size)

    def add_file_to_index(self, repo_id, version, path, obj_id, mtime, size):
        """Add/update a file to/in index.
        """
        if not is_valid_utf8(path):
            return

        extractor = ExtractorFactory.get_extractor(os.path.basename(path))
        content = extractor.extract(repo_id, version, obj_id, path) if extractor else None
        filename = os.path.basename(path)

        try:
            eid = self.find_file_eid(repo_id, path)
        except:
            logging.warning('failed to find_file_eid, %s(%s), %s(%s)',
                            repo_id, type(repo_id),
                            path, type(path))
            raise
        if eid:
            # This file already exists in index, we update it
            self.partial_update_file_content(eid, content, mtime, size)
        else:
            # This file does not exist in index
            suffix = get_file_suffix(filename)

            data = utf8_decode({
                'repo': repo_id,
                'path': path,
                'filename': filename,
                'suffix': suffix,
                'content': content,
                'is_dir': False,
                'mtime': mtime,
                'size': size
                # 'tags': get_repo_file_tags(repo_id, path)
            })
            self.es.index(index=self.INDEX_NAME,
                          doc_type=self.MAPPING_TYPE,
                          body=data,
                          id=_doc_id(repo_id, path))

    def update_repo_name_index(self, repo_id, version, obj_id):
        if not repo_data.get_repo_name_mtime_size(repo_id):
            return
        repo = repo_data.get_repo_name_mtime_size(repo_id)[0]
        mtime = repo["update_time"]
        size = repo["size"]
        repo_name = repo["name"]
        self.add_dir_to_index(repo_id, version, '/', obj_id, mtime, size, repo_name)

    def add_dir_to_index(self, repo_id, version, path, obj_id, mtime, size, repo_name=None): # pylint: disable=unused-argument
        """Add a dir to index.
        """
        if not is_valid_utf8(path):
            return

        if path == '/':
            filename = repo_name
        else:
            filename = os.path.basename(path)

        path = path + '/' if path != '/' else path
        eid = _doc_id(repo_id, path)

        data = utf8_decode({
            'repo': repo_id,
            'path': path,
            'filename': filename,
            'suffix': None,
            'content': None,
            'is_dir': True,
            'mtime': mtime,
            'size': size
        })
        self.es.index(
            index=self.INDEX_NAME,
            doc_type=self.MAPPING_TYPE,
            body=data,
            id=eid
        )

    def find_file_eid(self, repo_id, path):
        eid = _doc_id(repo_id, path)
        try:
            self.es.get(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=eid, _source_include=[])
            return eid
        except NotFoundError:
            return None

    def partial_update_file_content(self, eid, content, mtime, size):
        doc = {
            'content': content,
            'mtime': mtime,
            'size': size
        }

        self.es.update(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=eid, body=dict(doc=doc))

    def delete_files(self, repo_id, files):
        actions = []
        for path in files:
            eid = _doc_id(repo_id, path)
            actions.append({
                '_op_type': 'delete',
                '_index': self.INDEX_NAME,
                '_type': self.MAPPING_TYPE,
                '_id': eid
            })
            self.bulk(actions, ignore_not_found=True)
        self.refresh()

    def delete_dirs(self, repo_id, dirs):
        for path in dirs:
            path = path + '/' if path != '/' else path
            path = utf8_decode(path)
            self.delete_by_repo_path_prefix(repo_id, path)
        self.refresh()

    def delete_by_repo_path_prefix(self, repo_id, path_prefix):
        """Delete docs of dirs and all files/sub-dirs in those dirs of a repo.

        SQL: delete from repofiles where repo='xxx' and path like '/dir_xxx/%'
        """
        s = Search(using=self.es, index=self.INDEX_NAME).query(
            'term', repo=repo_id).query('prefix', path=path_prefix)
        s.delete()

    def update_files(self, repo_id, version, files):
        self.add_files(repo_id, version, files)

    def delete_repo(self, repo_id):
        if len(repo_id) != 36:
            return

        self.delete_by_repo(repo_id)
        self.refresh()

    def delete_by_repo(self, repo_id):
        """Delete all the docs of a repo.

        SQL: delete from repofiles where repo='xxx'
        """
        s = Search(using=self.es, index=self.INDEX_NAME).query(
            'term', repo=repo_id)
        s.delete()

    def search_files(self, repos_map, search_path, keyword, obj_desc=None, start=0, size=10):
        result = self.do_search(repos_map, search_path, keyword, obj_desc, start, size)

        def get_entries(result):
            def _expand(v):
                return v[0] if isinstance(v, list) else v

            hits = result.hits.hits
            ret = []
            for e in hits:
                fields = e.get('_source', {})
                for k, v in fields.copy().iteritems():
                    fields[k] = _expand(v)
                e['_source'] = fields
                ret.append(e)
            return ret

        total = result.hits.total
        ret = []

        for entry in get_entries(result):
            highlight = entry.get('highlight', {})

            content_highlight = '...'.join(highlight.get('content', []))
            d = entry['_source']
            try:
                is_dir = d['is_dir']
            except KeyError:
                # Compatible with existing entry that has not `is_dir` field in
                # index.
                is_dir = False
            r = {
                'repo_id': d['repo'],
                'fullpath': d['path'],
                'name': d['filename'],
                'score': entry['_score'],
                'content_highlight': content_highlight,
                'is_dir': is_dir,
            }
            ret.append(r)
        return ret, total

    def _make_keyword_query(self, keyword):
        keyword = utf8_decode(keyword)
        match_query_kwargs = {'minimum_should_match': '-25%'}
        if self.is_chinese():
            match_query_kwargs['analyzer'] = 'ik_smart'

        def _make_match_query(field, keyword, **kw):
            q = {'query': keyword}
            q.update(kw)
            return Q({"match": {field: q}})

        search_in_file_name = _make_match_query('filename', keyword, **match_query_kwargs)
        search_in_file_content = _make_match_query('content', keyword, **match_query_kwargs)

        searches = [search_in_file_name, search_in_file_content]
        if not self.is_chinese():
            # See https://www.elastic.co/guide/en/elasticsearch/guide/2.x/ngrams-compound-words.html
            # for how to specify the ngram minimum_should_match in a match query.
            search_in_file_name_ngram = Q({
                "match": {
                    "filename.ngram": {
                        "query": keyword,
                        "minimum_should_match": "80%",
                    }
                }
            })
            searches.append(search_in_file_name_ngram)

        return Q('bool', should=searches)

    def _add_repo_filter(self, search, repo_id):
        search = search.filter('term', repo=utf8_decode(repo_id))
        return search

    def _add_repos_filter(self, search, repos_map):
        # filter repo
        origin_repo_ids = [repo.id for repo in repos_map.values() if not repo.origin_repo_id]
        virtual_repos = [repo for repo in repos_map.values() if repo.origin_repo_id]

        repo_search_dsl = []
        if origin_repo_ids:
            # append all origin repo to terms
            repo_search_dsl.append(Q('terms', repo=utf8_decode(origin_repo_ids)))
        for repo in virtual_repos:
            # convert virtual_repo to origin_repo_id and origin_path
            temp_dsl = Q('term', repo=utf8_decode(repo.origin_repo_id)) & Q('prefix', path=repo.origin_path)
            repo_search_dsl.append(temp_dsl)

        if virtual_repos:
            # bool->should query
            repo_filter = reduce(or_, repo_search_dsl)
            search = search.filter(repo_filter)
            # search = search.query("bool", should=repo_search_dsl)
        else:
            # simple query
            repo_filter = repo_search_dsl[0]
            search = search.filter(repo_filter)
            # search.filter('bool', should=repo_search_dsl)

        return search

    def _add_suffix_filter(self, search, suffixes):
        if suffixes:
            if isinstance(suffixes, list):
                suffixes = [utf8_decode(x.lower()) for x in suffixes]
                search = search.filter('terms', suffix=suffixes)
            else:
                search = search.filter('term', suffix=suffixes.lower())
        return search

    def _add_path_filter(self, search, search_path):
        if search_path is None:
            return search
        search = search.filter('prefix', path=search_path)
        return search

    def _add_obj_type_filter(self, search, obj_type):
        if obj_type is None:
            return search
        elif obj_type == 'dir':
            search = search.filter('term', is_dir=True)
        else:
            search = search.filter('term', is_dir=False)
        return search

    def _get_search_range_dict(self, data_range):
        search_content = {}
        if data_range[0]:
            search_content['gte'] = data_range[0]
        if data_range[1]:
            search_content['lte'] = data_range[1]
        return search_content

    def is_valid_range(self, data_range):
        if not isinstance(data_range, tuple):
            return False
        if len(data_range) != 2:
            return False
        if all(e is None for e in data_range):
            return False
        return True


    def _add_time_range_filter(self, search, time_range):
        if not self.is_valid_range(time_range):
            return search
        search_content = self._get_search_range_dict(time_range)
        search = search.filter('range', mtime=search_content)
        return search

    def _add_size_range_filter(self, search, size_range):
        if not self.is_valid_range(size_range):
            return search
        search_content = self._get_search_range_dict(size_range)
        search = search.filter('range', size=search_content)
        return search

    def do_search(self, repos_map, search_path, keyword, obj_desc, start, size):
        """Search files with providing ``keyword``.

        Arguments:
        - `self`:
        - `repos_map`: A directory of repo_id and repo_obj.
        - `keyword`: A search keyword provided by user.
        - `suffixes`: A list of file suffixes need to be searched.
        - `start`: How many initial results should be skipped.
        - `size`:  How many results should be returned.
        """
        if isinstance(obj_desc, dict):
            suffixes = obj_desc.get('suffixes', None)
            obj_type = obj_desc.get('obj_type', None)
            time_range = obj_desc.get('time_range', None)
            size_range = obj_desc.get('size_range', None)
        else:
            suffixes = None
            obj_type = None
            time_range = None
            size_range = None

        search = Search(using=self.es, index=self.INDEX_NAME)

        # clean invalid repo
        for key in repos_map.keys():
            if not repos_map[key] or not hasattr(repos_map[key], 'origin_repo_id'):
                repos_map.pop(key)

        # Constraints on the search environment
        if len(repos_map) == 1:
            repo_id = repos_map.keys()[0]
            repo = repos_map.values()[0]

            if hasattr(repo, 'origin_path') and repo.origin_path:
                search_path = os.path.join(repo.origin_path, search_path.strip('/')) if search_path else repo.origin_path

            search = self._add_repo_filter(search, repo_id)
            search = self._add_path_filter(search, search_path)
        elif len(repos_map) > 1:
            search = self._add_repos_filter(search, repos_map)

        # Constraints on what you're searching for
        keyword_query = self._make_keyword_query(keyword)
        search = self._add_suffix_filter(search, suffixes)
        search = self._add_obj_type_filter(search, obj_type)

        search = self._add_time_range_filter(search, time_range)

        search = self._add_size_range_filter(search, size_range)

        search = search.query(keyword_query).source(
            include=['repo', 'path', 'filename', 'is_dir'])[start:start + size]

        search = search.highlight('content', type=seafes_config.highlight).highlight_options(
            pre_tags=['<b>'],
            post_tags=['</b>'],
            encoder='html',
            require_field_match=True
        )

        logger.debug(search.to_dict())
        resp = search.execute()
        return resp

def is_valid_utf8(path):
    if isinstance(path, unicode): # noqa: F821
        return True
    try:
        path.decode('utf8')
    except UnicodeDecodeError:
        return False
    else:
        return True

def _doc_id(repo_id, path):
    return utf8_decode(repo_id) + utf8_decode(path)
