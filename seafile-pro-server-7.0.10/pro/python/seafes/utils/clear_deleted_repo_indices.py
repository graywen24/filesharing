import logging


from seafes.repo_data import repo_data
from seafes.indexes import RepoStatusIndex, RepoFilesIndex
from seafes.connection import es_get_conn


def clear_deleted_repo_indices():
    repo_list = repo_data.get_all_repo_list()
    trash_repo_list = repo_data.get_all_trash_repo_list()
    repo_exist= [i['repo_id'] for i in repo_list]
    repo_exist.extend([i['repo_id'] for i in trash_repo_list])
    del repo_list
    del trash_repo_list

    try:
        status_index = RepoStatusIndex(es_get_conn())
        files_index = RepoFilesIndex(es_get_conn())
    except Exception as e:
        logging.error('Error:%s' % e)
        return
    repo_all = [r.get('id') for r in status_index.get_all_repos_from_index()]
    repo_deleted = set(repo_all) - set(repo_exist)
    logging.info("%d repos need to be deleted."% len(repo_deleted))
    for repo in repo_deleted:
        status_index.delete_repo(repo)
        files_index.delete_repo(repo)
        logging.info('repo %s has been removed' % repo)
    logging.info('Deleted repo removed success')

if __name__ == '__main__':
    clear_deleted_repo_indices()
