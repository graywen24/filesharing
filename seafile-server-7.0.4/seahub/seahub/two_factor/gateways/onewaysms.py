# Copyright (c) 2012-2016 Seafile Ltd.
import logging
import requests

from django.utils.translation import ugettext, pgettext

logger = logging.getLogger(__name__)



class Onewaysms(object):
    """
    apiusername=API79OLFWW2JC
    apipassword=API79OLFWW2JCTKH77
    mobileno=device.number
    senderid=1-Net_SG
    languagetype=1 for  en
    message=token
    """

    @staticmethod
    def send_sms(device, token):
        url = "http://gateway.onewaysms.sg:10002/api.aspx"
        messagecontent = ugettext('Your authentication token is %s.') % token

        values = {
            'mobileno': device.number,
            'message': messagecontent,
            'apiusername':'API79OLFWW2JC',
            'apipassword':'API79OLFWW2JCTKH77',
            'senderid':'1- Net_SG',
            'languagetype':'1'
        }
        #requests.post()
        
        x = requests.get(url, params=values)
        logger.info('get string result %s' , x)
        logger.info('get request result %s' , x.text)
        logger.info('line 80 Oneway SMS to %s: "Your token is: %s"', device.number, token)

