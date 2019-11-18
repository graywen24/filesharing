from seahub.test_utils import BaseTestCase
from django.http import HttpRequest
from seahub_extra.krb5_auth.middleware import RemoteKrbMiddleware

class TestRemoteKrbMiddleware(BaseTestCase):
    def setUp(self):
        self.middleware = RemoteKrbMiddleware()
        self.request = HttpRequest()
        self.request.session = self.client.session

    # def test_replace_username_suffix(self):
    #     assert False
