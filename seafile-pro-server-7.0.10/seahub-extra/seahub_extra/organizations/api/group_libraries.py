# Copyright (c) 2012-2016 Seafile Ltd.
import logging

from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle

from seahub.api2.permissions import IsProVersion
from seahub_extra.organizations.api.permissions import IsOrgAdmin
from seahub_extra.organizations.api.utils import check_org_admin
from seahub.api2.endpoints.admin.group_libraries import AdminGroupLibraries as SysAdminGroupLibraries
from seahub.api2.endpoints.admin.group_libraries import AdminGroupLibrary as SysAdminGroupLibrary

logger = logging.getLogger(__name__)


class AdminGroupLibraries(APIView):

    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def get(self, request, org_id, group_id, format=None):
        """ List all group repos in an org group.

        Permission checking:
        1. only admin can perform this action.
        """

        return SysAdminGroupLibraries().get(request, group_id, format)


class AdminGroupLibrary(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def delete(self, request, org_id, group_id, repo_id, format=None):
        """ Unshare repo from group

        Permission checking:
        1. only admin can perform this action.
        """
        return SysAdminGroupLibrary().delete(request, group_id, repo_id, format)
