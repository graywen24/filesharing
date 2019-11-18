import logging

from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView

from seahub.api2.throttling import UserRateThrottle
from seahub.api2.authentication import TokenAuthentication
from seahub.api2.permissions import IsProVersion
from seahub.api2.endpoints.admin.groups import AdminGroup as SysAdminGroup

from seahub_extra.organizations.api.permissions import IsOrgAdmin
from seahub_extra.organizations.api.utils import check_org_admin

logger = logging.getLogger(__name__)


class AdminGroup(APIView):

    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsOrgAdmin, IsProVersion)

    @check_org_admin
    def put(self, request, org_id, group_id):
        """ Admin update a group

        1. transfer a group.
        2. set group quota

        Permission checking:
        1. Admin user;
        """

        return SysAdminGroup().put(request, group_id)
