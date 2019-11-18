from seahub.test_utils import BaseTestCase
from seahub_extra.two_factor.models import StaticDevice, StaticToken


class StaticDeviceTest(BaseTestCase):
    def test_get_or_create(self):
        assert len(StaticDevice.objects.all()) == 0
        d = StaticDevice.get_or_create(self.user.username)
        assert d is not None
        assert len(StaticDevice.objects.all()) == 1

    def test_generate_token(self):
        assert len(StaticToken.objects.all()) == 0
        d = StaticDevice.get_or_create(self.user.username)
        d.generate_tokens()
        assert len(StaticToken.objects.all()) == 10
