# Copyright (c) 2012-2016 Seafile Ltd.
import logging

from django.conf import settings
import requests


logger = logging.getLogger(__name__)


class SeafMessenger(object):
    '''
    @staticmethod
    def make_call(device, token):
        logger.info('Fake call to %s: "Your call token is: %s"', device.number, token)
    @staticmethod
    def send_sms(device, token):
        api_token = settings.SEAF_MESSAGER_API_TOKEN
        url = settings.SEAF_MESSAGER_SMS_API
        logger.info("api_token %", api_token)
        print "url value", url
        values = {
            'phone_num': device.number,
            'code': token,
        }
        requests.post(url, data=values,
                      headers={'Authorization': 'Token %s' % api_token})
        logger.info('here is api_token %s',api_token)
        logger.info('Fake SMS to %s: "Your SMS token is: %s"', device, token)
    '''
    @staticmethod
    def send_sms(device, token):
        api_token = settings.SEAF_MESSAGER_API_TOKEN
        logger.info("here is token number", api_token)
        logger.info("here to get url")
        #url = settings.SEAF_MESSAGER_SMS_API
        url="http://gateway.onewaysms.sg:10002/api.aspx"

        values = {
            'mobileno': device.number,
            'message': token,
            'apiusername' : "xxxxx",
            'apipassword' : "xxxxx,
            'senderid' : "1-Net_SG",
            'languagetype' : "1"

        }
        requests.post()
        requests.post(url, data=values,
                      headers={'Authorization': 'Token %s' % api_token})
