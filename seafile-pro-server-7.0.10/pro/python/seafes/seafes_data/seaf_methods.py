from seafes.seafes_data.db import db

def get_all_repo_id_commit_id_by_limit(start, end):
    sql = """SELECT repo_id, commit_id
             FROM Branch WHERE name=%s
             AND repo_id NOT IN (SELECT repo_id from VirtualRepo) limit %s, %s"""
    param = ('master', start, end)
    return db.query(sql, param)

