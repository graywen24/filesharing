# coding: UTF-8

from .indexes import RepoFilesIndex
from .connection import es_get_conn

def es_search(repos_map, search_path, keyword, obj_desc, start, size):
    conn = es_get_conn()
    files_index = RepoFilesIndex(conn)
    return files_index.search_files(repos_map, search_path, keyword, obj_desc, start, size)
