# -*- coding: utf-8 -*-
SECRET_KEY = "4pw9f3!jc8n5*p2_-9rx&gj0mnda&!(-)x5z52-@pdam02t+k)"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'seahub_db',
        'USER': 'seafile',
        'PASSWORD': 'b334d6e7-aadd-45b1-8e84-1e747009bb36',
        'HOST': 'db',
        'PORT': '3306'
    }
}


CACHES = {
    'default': {
        'BACKEND': 'django_pylibmc.memcached.PyLibMCCache',
        'LOCATION': 'memcached:11211',
    },
    'locmem': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}
COMPRESS_CACHE_BACKEND = 'locmem'
TIME_ZONE = 'Etc/UTC'
FILE_SERVER_ROOT = "http://seafile.example.com/seafhttp"
