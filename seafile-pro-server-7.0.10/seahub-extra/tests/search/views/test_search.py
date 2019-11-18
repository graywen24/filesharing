from mock import patch
from django.conf.urls import patterns, include

import seahub
import seahub.urls
from seahub.test_utils import BaseTestCase

from seahub_extra.search.views import search

class SearchTest(BaseTestCase):
    urls = 'seahub.urls'

    def setUp(self):
        super(SearchTest, self).setUp()

        self.original_urls = seahub.urls.urlpatterns
        seahub.urls.urlpatterns += patterns(
            '',
            (r'^search/$', search),
        )

        self.url = '/search/'
        self.login_as(self.user)

    @patch('seahub_extra.search.views.search_repo_file_by_name')
    def test_can_search_in_repo(self, mock_search_repo_file_by_name):
        mock_search_repo_file_by_name.return_value = ([], 0)

        resp = self.client.get(self.url + '?q=test&search_repo=' + self.repo.id)
        self.assertEqual(200, resp.status_code)
        self.assertTemplateUsed(resp, 'search_results.html')

    @patch('seahub_extra.search.views.search_repo_file_by_name')
    def test_can_not_search_in_others_repo(self, mock_search_repo_file_by_name):
        self.logout()
        self.login_as(self.admin)

        mock_search_repo_file_by_name.return_value = ([], 0)

        resp = self.client.get(self.url + '?q=test&search_repo=' + self.repo.id)
        self.assertEqual(404, resp.status_code)

        self.logout()
