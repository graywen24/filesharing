from seahub.test_utils import BaseTestCase
from seahub_extra.two_factor.models import TOTPDevice
from seahub_extra.two_factor.oath import TOTP


class TOTPDeviceTest(BaseTestCase):
    def test_bin_key(self):
        assert len(TOTPDevice.objects.all()) == 0
        d = TOTPDevice.objects.create(user=self.user.username)
        assert d.bin_key is not None

        assert len(TOTPDevice.objects.all()) == 1

    # def test_verify_token(self):
    #     d = TOTPDevice.objects.create(user=self.user.username)

    #     totp = TOTP(d.bin_key, d.step, d.t0, d.digits)
    #     print totp
