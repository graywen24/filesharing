from django.conf.urls import patterns, include
from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from mock import patch
from constance import config

import seahub
import seahub.urls
from seahub.test_utils import BaseTestCase
from seahub_extra.two_factor.models import TOTPDevice
from seahub_extra.two_factor.forms import TOTPDeviceForm

@override_settings(ENABLE_TWO_FACTOR_AUTH=True)
class SetupViewTest(BaseTestCase):
    urls = 'seahub.urls'

    def setUp(self):
        super(SetupViewTest, self).setUp()

        self.original_urls = seahub.urls.urlpatterns
        seahub.urls.urlpatterns += patterns(
            '',
            (r'^profile/two_factor_authentication/', include('seahub_extra.two_factor.urls', 'two_factor')),
        )

        self.url = '/profile/two_factor_authentication/setup/'
        config.ENABLE_TWO_FACTOR_AUTH = 1
        self.login_as(self.user)

    def tearDown(self):
        self.clear_cache()

    @patch.object(TOTPDeviceForm, 'clean_token')
    def test_can_setup_with_totp(self, mock_clean_token):
        mock_clean_token.return_value = '123456'
        assert len(TOTPDevice.objects.all()) == 0

        # QR code page to let user enter token
        resp = self.client.post(self.url, {
            'setup_view-current_step': 'generator'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed('two_factor/core/setup.html')
        assert resp.context['wizard']['steps'].current == 'generator'
        print resp.context

        # user enter a "valid" token
        resp = self.client.post(self.url, {
            'setup_view-current_step': 'generator',
            'generator-token': '123'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('two_factor:backup_tokens'))

        assert len(TOTPDevice.objects.all()) == 1

    def test_invalid_totp_token(self):
        assert len(TOTPDevice.objects.all()) == 0

        # QR code page to let user enter token
        resp = self.client.post(self.url, {
            'setup_view-current_step': 'generator'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed('two_factor/core/setup.html')
        assert resp.context['wizard']['steps'].current == 'generator'

        # user enter invalid token
        resp = self.client.post(self.url, {
            'setup_view-current_step': 'generator',
            'generator-token': '123'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed('two_factor/core/setup.html')
        assert resp.context['wizard']['steps'].current == 'generator'
        assert 'Entered token is not valid.' in resp.content

        assert len(TOTPDevice.objects.all()) == 0
