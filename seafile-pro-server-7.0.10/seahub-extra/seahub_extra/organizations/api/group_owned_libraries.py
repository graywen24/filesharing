import logging

from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView

from seahub.api2.throttling import UserRateThrottle
from seahub.api2.authentication import TokenAuthentication
from seahub.api2.permissions import IsProVersion
from seahub_extra.organizations.api.permissions import IsOrgAdmin
from seahub_extra.organizations.api.utils import check_org_admin
from seahub.api2.endpoints.admin.group_owned_libraries import AdminGroupOwnedLibraries as SysAdminGroupOwnedLibraries
from seahub.api2.endpoints.admin.group_owned_libraries import AdminGroupOwnedLibrary as SysAdminGroupOwnedLibrary


logger = logging.getLogger(__name__)

class AdminGroupOwnedLibraries(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def post(self, request, org_id, group_id):
        """ Add a group owned library.
        """
        return SysAdminGroupOwnedLibraries().post(request, group_id)


class AdminGroupOwnedLibrary(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def delete(self, request, org_id, group_id, repo_id):
        """ Delete a group owned library.
        """
        return SysAdminGroupOwnedLibrary().delete(request, group_id, repo_id)
