# Copyright (c) 2012-2016 Seafile Ltd.
import logging

from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.permissions import IsProVersion
from seahub.api2.endpoints.admin.group_members import AdminGroupMembers as SysAdminGroupMembers
from seahub.api2.endpoints.admin.group_members import AdminGroupMember as SysAdminGroupMember
from seahub_extra.organizations.api.permissions import IsOrgAdmin
from seahub_extra.organizations.api.utils import check_org_admin

logger = logging.getLogger(__name__)


class AdminGroupMembers(APIView):

    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def get(self, request, org_id, group_id, format=None):
        """ List all group members

        Permission checking:
        1. only admin can perform this action.
        """
        return SysAdminGroupMembers().get(request, group_id, format)

    @check_org_admin
    def post(self, request, org_id, group_id):
        """
        Bulk add group members.

        Permission checking:
        1. only admin can perform this action.
        """
        return SysAdminGroupMembers().post(request, group_id)


class AdminGroupMember(APIView):

    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def put(self, request, org_id, group_id, email, format=None):
        """ update role of a group member

        Permission checking:
        1. only admin can perform this action.
        """
        return SysAdminGroupMember().put(request, group_id, email, format)

    @check_org_admin
    def delete(self, request, org_id, group_id, email, format=None):
        """ Delete an user from group

        Permission checking:
        1. only admin can perform this action.
        """
        return SysAdminGroupMember().delete(request, group_id, email, format)
