#coding: utf8
import logging

from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Search
from elasticsearch.helpers import scan

from .base import SeafileIndexBase

logger = logging.getLogger('seafes')

class RepoStatus(object):
    def __init__(self, repo_id, from_commit, to_commit):
        self.repo_id = repo_id
        self.from_commit = from_commit
        self.to_commit = to_commit

    def need_recovery(self):
        return self.to_commit is not None

class RepoStatusIndex(SeafileIndexBase):
    '''The repo-head index is used to store the status for each repo.

    For each repo:
    (1) before update: commit = <previously indexed commit>, updatingto = None
    (2) during updating: commit = <previously indexed commit>, updatingto = <current latest commit>
    (3) after updating: commit = <newly indexed commit>, updatingto = None

    When error occured during updating, the status is left in case (2). So the
    next time we update that repo, we can recover the failed process again.

    The elasticsearch document id for each repo in repo_head index is its repo
    id.
    '''

    INDEX_NAME = 'repo_head'
    MAPPING_TYPE = 'repo_commit'
    MAPPING = {
        '_source': {
            'enabled': True
        },
        'properties': {
            'repo': {
                'type' : 'string',
                'index': 'not_analyzed'
            },
            'commit': {
                'type' : 'string',
                'index': 'not_analyzed'
            },
            'updatingto': {
                'type' : 'string',
                'index': 'not_analyzed'
            }
        },
    }

    def __init__(self, es):
        super(RepoStatusIndex, self).__init__(es)
        self.create_index_if_missing()

    def get_repo_status(self, repo_id):
        """Query status of a repo form ``repo_head`` index, add this repo if
        not found.

        Arguments:
        - `self`:
        - `repo_id`:

        Returns:
            A ``RepoStatus`` instance and a flag indicates whether this repo
            is corrupted.
        """
        try:
            # we use repo_id as the doucment id of repo_head index
            doc = self.es.get(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=repo_id)
            doc = doc['_source']
        except NotFoundError:
            doc = None

        commit_id = updatingto = None
        if doc is not None:
            commit_id = doc.get('commit', None)
            updatingto = doc.get('updatingto', None)
            return RepoStatus(repo_id, commit_id, updatingto)

        # repo not found in the repo_head index
        data = {
            'commit': None,
            'updatingto': None
        }
        try:
            self.es.index(
                index=self.INDEX_NAME,
                doc_type=self.MAPPING_TYPE,
                body=data,
                id=repo_id
            )
        except:
            logger.exception('Failed to add repo to index: %s', repo_id)
            raise

        self.refresh()
        return RepoStatus(repo_id, commit_id, updatingto)

    def begin_update_repo(self, repo_id, old_commit_id, new_commit_id):
        doc = {
            'commit': old_commit_id,
            'updatingto': new_commit_id,
        }
        self.es.update(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=repo_id, body=dict(doc=doc))
        self.refresh()

    def finish_update_repo(self, repo_id, commit_id):
        doc = {
            'commit': commit_id,
            'updatingto': None,
        }
        self.es.update(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=repo_id, body=dict(doc=doc))
        self.refresh()

    def delete_repo(self, repo_id):
        if len(repo_id) != 36:
            return

        self.es.delete(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=repo_id)
        self.refresh()

        logger.debug('delete_repo called on %s', repo_id)

    def get_all_repos_from_index(self):
        resp = scan(self.es,
                query={"query": {"match_all": {}}},
                index=self.INDEX_NAME,
                doc_type=self.MAPPING_TYPE
        )
        return [{'id': entry['_id']} for entry in resp]
