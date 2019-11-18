import sys
from ConfigParser import ConfigParser

if len(sys.argv) != 2:
    print >> sys.stderr, 'check-db-type.py <seafile-config-file>'

seafile_conf_file = sys.argv[1]

parser = ConfigParser()
parser.read(seafile_conf_file)

if not parser.has_option('database', 'type'):
    print 'sqlite'
else:
    db_type = parser.get('database', 'type')
    if db_type == 'sqlite':
        print 'sqlite'
    elif db_type == 'mysql':
        print 'mysql'
    elif db_type == 'pgsql':
        print 'pgsql'
    else:
        print 'unknown'
