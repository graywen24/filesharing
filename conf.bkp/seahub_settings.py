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
FILE_SERVER_ROOT = "http://localhost/seafhttp"
ENABLE_TOW_FACTOR_AUTH = True

TWO_FACTOR_SMS_GATEWAY = 'seahub.two_factor.gateways.onewaysms.Onewaysms'
#TWO_FACTOR_SMS_GATEWAY = 'seahub.two_factor.gateways.twilio.gateway.Twilio'
#TWO_FACTOR_SMS_GATEWAY = 'seahub.two_factor.gateways.fake.Fake'

TWILIO_ACCOUNT_SID = ''

TWILIO_AUTH_TOKEN = ''

TWILIO_CALLER_ID = '+12512748580'

EXTRA_MIDDLEWARE_CLASSES = (
    'seahub.two_factor.gateways.twilio.middleware.ThreadLocals',
)
DEBUG = True
