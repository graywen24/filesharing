# Copyright (c) 2012-2016 Seafile Ltd.
import os

# haiwen/
# |___seafile-pro-server-1.7.0/
#         |____ seahub
#             |____ seahub/
#                  |____ setings.py
#         |____ seahub-extra
#             |____ seahub_extra/
#                  |____ seahub_extra_settings.py (this file)
# |___pro-data
#    |___ search index
# |___ccnet/
# |___seafile-data/
# |___conf/
#    |___ seafevents.conf

d = os.path.dirname

topdir = d(d(d(d(os.path.abspath(__file__)))))

EVENTS_CONFIG_FILE = os.environ.get('EVENTS_CONFIG_FILE',
    os.path.join(topdir, 'conf', 'seafevents.conf'))


if not os.path.exists(EVENTS_CONFIG_FILE):
    del EVENTS_CONFIG_FILE

del d, topdir

EXTRA_INSTALLED_APPS = (
    "seahub_extra.search",
    "seahub_extra.sysadmin_extra",
    'seahub_extra.organizations',
    'seahub_extra.krb5_auth',
    'seahub_extra.django_cas_ng',
)

EXTRA_MIDDLEWARE_CLASSES = (
    'seahub_extra.organizations.middleware.RedirectMiddleware',
)

EXTRA_AUTHENTICATION_BACKENDS = (
    'seahub_extra.django_cas_ng.backends.CASBackend',
)

USE_PDFJS = False

ENABLE_SYSADMIN_EXTRA = True

MULTI_TENANCY = False

ENABLE_UPLOAD_FOLDER = True

ENABLE_FOLDER_PERM = True
