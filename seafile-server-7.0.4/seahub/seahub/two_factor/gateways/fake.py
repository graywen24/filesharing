# Copyright (c) 2012-2016 Seafile Ltd.
import logging
import requests

from django.utils.translation import ugettext, pgettext

logger = logging.getLogger(__name__)


class Fake(object):
    """
    Prints the tokens to the logger. You will have to set the message level of
    the ``two_factor`` logger to ``INFO`` for them to appear in the console.
    Useful for local development. You should configure your logging like this::

        LOGGING = {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                'two_factor': {
                    'handlers': ['console'],
                    'level': 'INFO',
                }
            }
        }
    """
    @staticmethod
    def make_call(device, token):
        logger.info('Fake call to %s: "Your token is: %s"', device.number, token)

    @staticmethod
    def send_sms(device, token):
        logger.info('here show =========')
        logger.info('Fake SMS to %s: "Your token is: %s"', device.number, token)
        logger.info('Fake SMS device is  %s',device)
        logger.debug('Fake SMS to %s: "Your token is: %s"', device.number, token)


class Onewaysms(object):
    """
    apiusername=API79OLFWW2JC
    apipassword=API79OLFWW2JCTKH77
    mobileno=device.number
    senderid=1-Net_SG
    languagetype=1 for  en
    message=token


    def send_sms(self, device, token):
        logging.info("twillow token is %s", token)
        body = ugettext('Your authentication token is %s') % token
        self.client.sms.messages.create(
            to=device.number,
            from_=getattr(settings, 'TWILIO_CALLER_ID'),
            body=body)

    """

    @staticmethod
    def send_sms(device, token):
        url = "http://gateway.onewaysms.sg:10002/api.aspx"
        messagecontent = ugettext('Your authentication token is %s') % token

        values = {
            'mobileno': device.number,
            'message': messagecontent,
            'apiusername':'xxxx',
            'apipassword':'xxxxxx',
            'senderid':'1- Net_SG',
            'languagetype':'1'
        }
        #requests.post()
        
        x = requests.get(url, params=values)
        logger.info('get string result %s' , x)
        logger.info('get request result %s' , x.text)
        logger.info('line 80 Oneway SMS to %s: "Your token is: %s"', device.number, token)


