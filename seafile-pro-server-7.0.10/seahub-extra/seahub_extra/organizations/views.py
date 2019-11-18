# Copyright (c) 2012-2016 Seafile Ltd.
# encoding: utf-8

import logging
import os
import json
from types import FunctionType
from urlparse import urlparse

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render

from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _

import seaserv
from seaserv import seafile_api, get_group, get_repo, \
    get_group_members, ccnet_api
from pysearpc import SearpcError

from seahub.auth import login
from seahub.auth.decorators import login_required, login_required_ajax
from seahub.base.decorators import require_POST
from seahub.base.accounts import User
from seahub.base.models import UserLastLogin
from seahub.constants import DEFAULT_USER
from seahub.forms import AddUserForm
from seahub.group.views import remove_group_common
from seahub.group.utils import group_id_to_name
from seahub.profile.models import Profile
from seahub.profile.utils import convert_contact_emails
from seahub.signals import repo_deleted
from seahub.share.models import FileShare, OrgFileShare
from seahub.utils import is_valid_username, IS_EMAIL_CONFIGURED, \
    get_service_url, string2list, get_file_audit_events, \
    get_file_update_events, get_perm_audit_events, EVENTS_ENABLED
from seahub.utils.timeutils import utc_to_local
from seahub.utils.file_size import get_file_size_unit
from seahub.utils.auth import get_login_bg_image_path
from seahub.views.sysadmin import email_user_on_activation, populate_user_info, \
        send_user_add_mail, send_user_reset_email
from seahub.base.templatetags.seahub_tags import email2nickname
from seahub.api2.endpoints.group_owned_libraries import get_group_id_by_repo_owner

from seahub_extra.organizations.signals import org_created
from seahub_extra.organizations.decorators import org_staff_required
from seahub_extra.organizations.forms import OrgRegistrationForm
from seahub_extra.organizations.settings import ORG_AUTO_URL_PREFIX, ORG_MEMBER_QUOTA_ENABLED

from seahub.settings import INIT_PASSWD, SEND_EMAIL_ON_RESETTING_USER_PASSWD, \
        SEND_EMAIL_ON_ADDING_SYSTEM_MEMBER

# Get an instance of a logger
logger = logging.getLogger(__name__)

########## ccnet rpc wrapper
def create_org(org_name, url_prefix, creator):
    return seaserv.create_org(org_name, url_prefix, creator)

def count_orgs():
    return seaserv.ccnet_threaded_rpc.count_orgs()

def get_org_by_url_prefix(url_prefix):
    return seaserv.ccnet_threaded_rpc.get_org_by_url_prefix(url_prefix)

def set_org_user(org_id, username, is_staff=False):
    return seaserv.ccnet_threaded_rpc.add_org_user(org_id, username,
                                                   int(is_staff))

def unset_org_user(org_id, username):
    return seaserv.ccnet_threaded_rpc.remove_org_user(org_id, username)

def org_user_exists(org_id, username):
    return seaserv.ccnet_threaded_rpc.org_user_exists(org_id, username)

def get_org_groups(org_id, start, limit):
    return seaserv.ccnet_threaded_rpc.get_org_groups(org_id, start, limit)

def get_org_id_by_group(group_id):
    return seaserv.ccnet_threaded_rpc.get_org_id_by_group(group_id)

def remove_org_group(org_id, group_id, username):
    remove_group_common(group_id, username)
    seaserv.ccnet_threaded_rpc.remove_org_group(org_id, group_id)

def is_org_staff(org_id, username):
    return seaserv.ccnet_threaded_rpc.is_org_staff(org_id, username)

def set_org_staff(org_id, username):
    return seaserv.ccnet_threaded_rpc.set_org_staff(org_id, username)

def unset_org_staff(org_id, username):
    return seaserv.ccnet_threaded_rpc.unset_org_staff(org_id, username)

########## seafile rpc wrapper
def get_org_user_self_usage(org_id, username):
    """

    Arguments:
    - `org_id`:
    - `username`:
    """
    return seaserv.seafserv_threaded_rpc.get_org_user_quota_usage(org_id, username)

def get_org_user_quota(org_id, username):
    return seaserv.seafserv_threaded_rpc.get_org_user_quota(org_id, username)

def get_org_quota(org_id):
    return seaserv.seafserv_threaded_rpc.get_org_quota(org_id)

def is_org_repo(org_id, repo_id):
    return True if seaserv.seafserv_threaded_rpc.get_org_id_by_repo_id(
        repo_id) == org_id else False

########## views
@login_required_ajax
def org_add(request):
    """Handle ajax request to add org, and create org owner.

    Arguments:
    - `request`:
    """
    if not request.user.is_staff or request.method != 'POST':
        raise Http404

    content_type = 'application/json; charset=utf-8'

    url_prefix = gen_org_url_prefix(3)
    post_data = request.POST.copy()
    post_data['url_prefix'] = url_prefix
    form = OrgRegistrationForm(post_data)
    if form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password1']
        org_name = form.cleaned_data['org_name']
        url_prefix = form.cleaned_data['url_prefix']

        try:
            new_user = User.objects.create_user(email, password,
                                                is_staff=False, is_active=True)
        except User.DoesNotExist as e:
            logger.error(e)
            err_msg = 'Fail to create organization owner %s.' % email
            return HttpResponse(json.dumps({'error': err_msg}),
                                status=403, content_type=content_type)
        create_org(org_name, url_prefix, new_user.username)

        return HttpResponse(json.dumps({'success': True}),
                            content_type=content_type)
    else:
        try:
            err_msg = form.errors.values()[0][0]
        except IndexError:
            err_msg = form.errors.values()[0]
        return HttpResponse(json.dumps({'error': str(err_msg)}),
                            status=400, content_type=content_type)

def gen_org_url_prefix(max_trial=None):
    """Generate organization url prefix automatically.
    If ``max_trial`` is large than 0, then re-try that times if failed.

    Arguments:
    - `max_trial`:

    Returns:
        Url prefix if succed, otherwise, ``None``.
    """
    def _gen_prefix():
        url_prefix = 'org_' + get_random_string(
            6, allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789')
        if get_org_by_url_prefix(url_prefix) is not None:
            logger.info("org url prefix, %s is duplicated" % url_prefix)
            return None
        else:
            return url_prefix

    try:
        max_trial = int(max_trial)
    except (TypeError, ValueError):
        max_trial = 0

    while max_trial >= 0:
        ret = _gen_prefix()
        if ret is not None:
            return ret
        else:
            max_trial -= 1

    logger.warn("Failed to generate org url prefix, retry: %d" % max_trial)
    return None

def org_register(request):
    """Allow a new user to register an organization account. A new
    organization will be created associate with that user.

    Arguments:
    - `request`:
    """
    login_bg_image_path = get_login_bg_image_path()

    if request.method == 'POST':
        form = OrgRegistrationForm(request.POST)

        if ORG_AUTO_URL_PREFIX:
            # generate url prefix automatically
            url_prefix = gen_org_url_prefix(3)
            if url_prefix is None:
                messages.error(request, "Failed to create organization account, please try again later.")
                return render(request, 'organizations/org_register.html', {
                    'form': form,
                    'login_bg_image_path': login_bg_image_path,
                    'org_auto_url_prefix': ORG_AUTO_URL_PREFIX,
                })

            post_data = request.POST.copy()
            post_data['url_prefix'] = url_prefix
            form = OrgRegistrationForm(post_data)

        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']
            org_name = form.cleaned_data['org_name']
            url_prefix = form.cleaned_data['url_prefix']

            new_user = User.objects.create_user(email, password,
                                                is_staff=False, is_active=True)
            create_org(org_name, url_prefix, new_user.username)
            new_org = get_org_by_url_prefix(url_prefix)
            org_created.send(sender=None, org=new_org)

            if name:
                Profile.objects.add_or_update(new_user.username, name)

            # login the user
            new_user.backend = settings.AUTHENTICATION_BACKENDS[0]
            login(request, new_user)

            return HttpResponseRedirect(reverse('libraries'))
    else:
        form = OrgRegistrationForm()

    service_url = get_service_url()
    up = urlparse(service_url)
    service_url_scheme = up.scheme
    service_url_remaining = up.netloc + up.path

    return render(request, 'organizations/org_register.html', {
        'form': form,
        'login_bg_image_path': login_bg_image_path,
        'service_url_scheme': service_url_scheme,
        'service_url_remaining': service_url_remaining,
        'org_auto_url_prefix': ORG_AUTO_URL_PREFIX,
    })

@login_required
@org_staff_required
def org_user_admin(request):
    """List organization user.
    """
    org = request.user.org

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '25'))
    except ValueError:
        current_page = 1
        per_page = 25
    users_plus_one = ccnet_api.get_org_users_by_url_prefix(
        org.url_prefix, per_page * (current_page - 1), per_page + 1)
    if len(users_plus_one) == per_page + 1:
        page_next = True
    else:
        page_next = False

    users = users_plus_one[:per_page]
    last_logins = UserLastLogin.objects.filter(username__in=[x.email for x in users])
    for user in users:
        if user.props.id == request.user.id:
            user.is_self = True

        populate_user_info(user)

        try:
            user.self_usage = get_org_user_self_usage(org.org_id, user.email)
            user.share_usage = 0 #seafile_api.get_user_share_usage(user.email)
            user.quota = get_org_user_quota(org.org_id, user.email)
        except SearpcError as e:
            logger.error(e)
            user.self_usage = -1
            user.share_usage = -1
            user.quota = -1

        user.is_org_staff = is_org_staff(org.org_id, user.email)

        # populate user last login time
        user.last_login = None
        for last_login in last_logins:
            if last_login.username == user.email:
                user.last_login = last_login.last_login

    return render(request, 'organizations/org_user_admin.html', {
            'users': users,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
        })

@login_required
@org_staff_required
def org_useradmin_admins(request):
    """List organization admin user.
    """
    org = request.user.org

    admin_users = []
    not_admin_users = []
    users = ccnet_api.get_org_users_by_url_prefix(org.url_prefix, -1, -1)
    last_logins = UserLastLogin.objects.filter(username__in=[x.email for x in users])

    user_self = None
    for user in users:
        populate_user_info(user)

        if is_org_staff(org.org_id, user.email):
            try:
                user.self_usage = get_org_user_self_usage(org.org_id, user.email)
                user.share_usage = 0 #seafile_api.get_user_share_usage(user.email)
                user.quota = get_org_user_quota(org.org_id, user.email)
            except SearpcError as e:
                logger.error(e)
                user.self_usage = -1
                user.share_usage = -1
                user.quota = -1

            # populate user last login time
            user.last_login = None
            for last_login in last_logins:
                if last_login.username == user.email:
                    user.last_login = last_login.last_login

            # set current user at the first of the user list
            if user.id == request.user.id:
                user.is_self = True
                user_self = user
                continue
            else:
                admin_users.append(user)
        else:
            not_admin_users.append(user)

    if user_self:
        admin_users.insert(0, user_self)

    return render(request, 'organizations/org_useradmin_admins.html', {
            'users': admin_users,
            'not_admin_users': not_admin_users,
        })

@login_required
@org_staff_required
def org_user_add(request):
    """Added an organization user, check member quota before adding.
    """
    if request.method != 'POST':
        raise Http404

    content_type = 'application/json; charset=utf-8'

    # check plan
    result = {}
    url_prefix = request.user.org.url_prefix
    org_members = len(ccnet_api.get_org_users_by_url_prefix(url_prefix, -1, -1))

    if ORG_MEMBER_QUOTA_ENABLED:
        from seahub_extra.organizations.models import OrgMemberQuota
        org_members_quota = OrgMemberQuota.objects.get_quota(request.user.org.org_id)
        if org_members_quota is not None and org_members >= org_members_quota:
            result['error'] = 'Failed. You can only invite %d members.' % org_members_quota
            return HttpResponse(json.dumps(result), status=403,
                                content_type=content_type)

    post_values = request.POST.copy()
    post_email = request.POST.get('email', '')
    post_role = request.POST.get('role', DEFAULT_USER)
    post_values.update({'email': post_email.lower(), 'role': post_role})

    form = AddUserForm(post_values)
    if form.is_valid():
        email = form.cleaned_data['email']
        name = form.cleaned_data['name']
        password = form.cleaned_data['password1']

        try:
            user = User.objects.create_user(email, password, is_staff=False,
                                            is_active=True)
        except User.DoesNotExist as e:
            logger.error(e)
            err_msg = _(u'Fail to add user %s.') % email
            return HttpResponse(json.dumps({'error': err_msg}),
                                status=403, content_type=content_type)

        if user and name:
            Profile.objects.add_or_update(username=user.username, nickname=name)

        org_id = request.user.org.org_id
        set_org_user(org_id, user.username)

        # refresh user object
        user = User.objects.get(user.username)
        if IS_EMAIL_CONFIGURED:
            if SEND_EMAIL_ON_ADDING_SYSTEM_MEMBER:
                try:
                    send_user_add_mail(request, email, password)
                    messages.success(request, _(u'Successfully added user %s. An email notification has been sent.') % user.contact_email)
                except Exception, e:
                    logger.error(str(e))
                    messages.success(request, _(u'Successfully added user %s. An error accurs when sending email notification, please check your email configuration.') % user.contact_email)
            else:
                messages.success(request, _(u'Successfully added user %s.') % user.contact_email)
        else:
            messages.success(request, _(u'Successfully added user %s. But email notification can not be sent, because Email service is not properly configured.') % user.contact_email)

        return HttpResponse(json.dumps({'success': True}),
                            content_type=content_type)
    else:
        return HttpResponse(json.dumps({'error': str(form.errors)}),
                            status=400, content_type=content_type)

@login_required
@org_staff_required
def org_user_search(request):
    """Search an organization user.
    """
    search_patt = request.GET.get('email', '')
    org = request.user.org
    org_users = ccnet_api.get_org_users_by_url_prefix(org.url_prefix, -1, -1)

    results = []
    if search_patt:
        for u in org_users:
            user = User.objects.get(u.email)
            if search_patt in user.username or search_patt in user.contact_email:
                results.append(user)

        last_logins = UserLastLogin.objects.filter(
            username__in=[x.email for x in results])
        for user in results:
            try:
                user.self_usage = seafile_api.get_user_self_usage(user.email)
                user.share_usage = seafile_api.get_user_share_usage(user.email)
                user.quota = get_org_user_quota(org.org_id, user.email)
            except SearpcError as e:
                logger.error(e)
                user.self_usage = -1
                user.share_usage = -1
                user.quota = -1

            user.is_org_staff = is_org_staff(org.org_id, user.email)
            # populate user last login time
            user.last_login = None
            for last_login in last_logins:
                if last_login.username == user.email:
                    user.last_login = last_login.last_login

    return render(request, 'organizations/user_search.html', {
            'users': results,
            'email': search_patt,
            })

@login_required
@org_staff_required
@require_POST
def org_user_remove(request, user_id):
    """Remove an organization user"""
    referer = request.META.get('HTTP_REFERER', None)
    next = reverse('org_user_admin') if referer is None else referer

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        messages.error(request, _(u'Failed to delete: the user does not exist'))
        return HttpResponseRedirect(next)

    org = request.user.org
    if not org_user_exists(org.org_id, user.username):
        messages.error(request, 'Failed to delete: the user does not belong to the organization.')
        return HttpResponseRedirect(next)

    if org.creator == user.username:
        messages.error(request, 'Failed to delete: the user is an organization creator')
        return HttpResponseRedirect(next)

    org_repos = seafile_api.get_org_owned_repo_list(org.org_id, user.username)
    for repo in org_repos:
        seafile_api.remove_repo(repo.id)

    user.delete()
    unset_org_user(org.org_id, user.username)

    messages.success(request, _('Successfully deleted %s') % user.name)
    return HttpResponseRedirect(next)

@login_required
@org_staff_required
@require_POST
def org_user_reset(request, user_id):
    """Reset an organization user's password.
    """
    referer = request.META.get('HTTP_REFERER', None)
    next = reverse('org_user_admin') if referer is None else referer

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        messages.error(request, 'Failed to reset password: the user does not exist')
        return HttpResponseRedirect(next)

    org = request.user.org
    if not org_user_exists(org.org_id, user.username):
        messages.error(request, 'Failed to reset password: the user does not belong to the organization.')
        return HttpResponseRedirect(next)

    if isinstance(INIT_PASSWD, FunctionType):
        new_password = INIT_PASSWD()
    else:
        new_password = INIT_PASSWD
    user.set_password(new_password)
    user.save()

    # send password reset email
    if IS_EMAIL_CONFIGURED:
        if SEND_EMAIL_ON_RESETTING_USER_PASSWD:
            try:
                send_user_reset_email(request, user.email, new_password)
                msg = _('Successfully reset password to %(passwd)s, an email has been sent to %(user)s.') % \
                    {'passwd': new_password, 'user': user.contact_email}
                messages.success(request, msg)
            except Exception as e:
                logger.error(str(e))
                msg = _('Successfully reset password to %(passwd)s, but failed to send email to %(user)s, please check your email configuration.') % \
                    {'passwd': new_password, 'user': user.contact_email}
                messages.success(request, msg)
        else:
            messages.success(request, _(u'Successfully reset password to %(passwd)s for user %(user)s.') % \
                             {'passwd': new_password,'user': user.contact_email})
    else:
        messages.success(request, _(u'Successfully reset password to %(passwd)s for user %(user)s. But email notification can not be sent, because Email service is not properly configured.') % \
                             {'passwd': new_password,'user': user.contact_email})

    return HttpResponseRedirect(next)

@login_required
@org_staff_required
def org_user_make_admin(request, user_id):
    """Set user as organization admin."""
    referer = request.META.get('HTTP_REFERER', None)
    next = reverse('org_user_admin') if referer is None else referer

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        messages.error(request, 'Failed to set admin: the user does not exist')
        return HttpResponseRedirect(next)

    org = request.user.org
    if not org_user_exists(org.org_id, user.username):
        messages.error(request, 'Failed to set admin: the user does not belong to the organization.')
        return HttpResponseRedirect(next)

    set_org_staff(org.org_id, user.username)
    messages.success(request, _(u'Successfully set %s as admin.') % user.name)
    return HttpResponseRedirect(next)

@login_required
@org_staff_required
@require_POST
def org_user_remove_admin(request, user_id):
    """Unset organization user admin."""
    referer = request.META.get('HTTP_REFERER', None)
    next = reverse('org_user_admin') if referer is None else referer

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        messages.error(request, _(u'Failed to revoke admin: the user does not exist'))
        return HttpResponseRedirect(next)

    org = request.user.org
    if not org_user_exists(org.org_id, user.username):
        messages.error(request, 'Failed to revoke admin: the user does not belong to the organization.')
        return HttpResponseRedirect(next)

    unset_org_staff(org.org_id, user.username)
    messages.success(request, _(u'Successfully revoke the admin permission of %s') % user.name)
    return HttpResponseRedirect(next)

@login_required
@org_staff_required
def org_repo_admin(request):
    """Show organization libraries.
    """
    org_id = request.user.org.org_id

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '25'))
    except ValueError:
        current_page = 1
        per_page = 25

    repos_all = seafile_api.get_org_repo_list(org_id,
                                              per_page * (current_page -1),
                                              per_page + 1)
    repos = repos_all[:per_page]
    if len(repos_all) == per_page + 1:
        page_next = True
    else:
        page_next = False

    repos = filter(lambda r: not r.is_virtual, repos)

    # get repo id owner dict
    all_repo_owner = []
    repo_id_owner_dict = {}
    for repo in repos:
        repo_owner = seafile_api.get_org_repo_owner(repo.id)
        all_repo_owner.append(repo_owner)
        repo_id_owner_dict[repo.id] = repo_owner

    # Use dict to reduce memcache fetch cost in large for-loop.
    name_dict = {}
    for email in set(all_repo_owner):
        if email not in name_dict:
            if '@seafile_group' in email:
                group_id = get_group_id_by_repo_owner(email)
                group_name = group_id_to_name(group_id)
                name_dict[email] = group_name
            else:
                name_dict[email] = email2nickname(email)

    for repo in repos:
        repo_owner = repo_id_owner_dict[repo.id]
        repo.owner = repo_owner
        repo.owner_name = name_dict.get(repo.owner, '')

        if '@seafile_group' in repo_owner:
            repo.is_department_repo = True
            group_id = get_group_id_by_repo_owner(repo_owner)
            repo.group_id = group_id
        else:
            repo.is_department_repo = False
            repo.group_id = ''

    return render(request, 'organizations/org_repo_admin.html', {
            'repos': repos,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@org_staff_required
def org_repo_transfer(request):
    """Transfer a repo to others.
    """
    if request.method != 'POST':
        raise Http404

    repo_id = request.POST.get('repo_id', None)
    new_owner = request.POST.get('email', None)
    next = request.META.get('HTTP_REFERER', reverse(org_repo_admin))

    if not repo_id and not new_owner:
        messages.error(request, 'Failed to transfer, invalid arguments.')
        return HttpResponseRedirect(next)

    # permission checking
    org_id = request.user.org.org_id
    if not org_user_exists(org_id, new_owner) or \
            not is_valid_username(new_owner):
        messages.error(request, 'Failed to transfer, user does not exist.')
        return HttpResponseRedirect(next)

    if not is_org_repo(org_id, repo_id):
        messages.error(request, 'Failed to transfer, library does not exist.')
        return HttpResponseRedirect(next)

    repo_owner = seafile_api.get_org_repo_owner(repo_id)

    # get repo shared to user/group list
    shared_users = seafile_api.list_org_repo_shared_to(org_id,
            repo_owner, repo_id)
    shared_groups = seafile_api.list_org_repo_shared_group(org_id,
            repo_owner, repo_id)

    # get all pub repos
    pub_repos = seaserv.seafserv_threaded_rpc.list_org_inner_pub_repos_by_owner(
            org_id, repo_owner)

    seafile_api.set_org_repo_owner(org_id, repo_id, new_owner)
    messages.success(request, _(u'Successfully transfered 1 item.'))

    # reshare repo to user
    for shared_user in shared_users:
        shared_username = shared_user.user

        if new_owner == shared_username:
            continue

        seaserv.seafserv_threaded_rpc.org_add_share(org_id, repo_id,
                new_owner, shared_username, shared_user.perm)

    # reshare repo to group
    for shared_group in shared_groups:
        shared_group_id = shared_group.group_id

        if not ccnet_api.is_group_user(shared_group_id, new_owner):
            continue

        seafile_api.add_org_group_repo(repo_id, org_id,
                shared_group_id, new_owner, shared_group.perm)

    # check if current repo is pub-repo
    # if YES, reshare current repo to public
    for pub_repo in pub_repos:
        if repo_id != pub_repo.id:
            continue

        seaserv.seafserv_threaded_rpc.set_org_inner_pub_repo(
                org_id, repo_id, pub_repo.permission)

        break

    return HttpResponseRedirect(next)

@login_required
@org_staff_required
def org_repo_delete(request, repo_id):
    """Delete a repo.
    """
    if request.method != 'POST':
        raise Http404

    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = reverse("org_repo_admin")

    repo = seafile_api.get_repo(repo_id)
    if not repo:
        raise Http404
    repo_name = repo.name

    org_id = request.user.org.org_id
    if not is_org_repo(org_id, repo_id):
        messages.error(request, 'Failed to delete, library does not exist.')
        return HttpResponseRedirect(next)

    usernames = seaserv.get_related_users_by_org_repo(org_id, repo_id)
    repo_owner = seafile_api.get_org_repo_owner(repo_id)

    seafile_api.remove_repo(repo_id)
    repo_deleted.send(sender=None, org_id=org_id, usernames=usernames,
                      repo_owner=repo_owner, repo_id=repo_id,
                      repo_name=repo_name)

    messages.success(request, _(u'Successfully deleted.'))
    return HttpResponseRedirect(next)

def list_org_repos_by_name_and_owner(org_id, repo_name, owner):
    repos = []
    owned_repos = seafile_api.get_org_owned_repo_list(org_id, owner)
    for repo in owned_repos:
        if repo_name.lower() in repo.name.lower():
            repo.owner = owner
            repos.append(repo)
    return repos

def list_org_repos_by_name(org_id, repo_name):
    repos = []
    repos_all = seafile_api.get_org_repo_list(org_id, -1, -1)
    for repo in repos_all:
        if repo_name.lower() in repo.name.lower():
            try:
                repo.owner = seafile_api.get_org_repo_owner(repo.id)
            except SearpcError:
                repo.owner = "failed to get"
            repos.append(repo)
    return repos

def list_org_repos_by_owner(org_id, owner):
    repos = seafile_api.get_org_owned_repo_list(org_id, owner)
    for e in repos:
        e.owner = owner
    return repos

@login_required
@org_staff_required
def org_repo_search(request):
    """Search an organization repo.
    """
    repo_name = request.GET.get('name', '')
    owner = request.GET.get('owner', '')
    org_id = request.user.org.org_id
    repos = []

    if repo_name and owner:  # search by name and owner
        repos = list_org_repos_by_name_and_owner(org_id, repo_name, owner)
        for repo in repos:
            repo.owner_name = email2nickname(owner)
            repo.is_department_repo = False
            repo.group_id = ''

    elif repo_name:     # search by name
        repos = list_org_repos_by_name(org_id, repo_name)

        # get repo id owner dict
        all_repo_owner = []
        repo_id_owner_dict = {}
        for repo in repos:
            repo_owner = seafile_api.get_org_repo_owner(repo.id)
            all_repo_owner.append(repo_owner)
            repo_id_owner_dict[repo.id] = repo_owner

        # Use dict to reduce memcache fetch cost in large for-loop.
        name_dict = {}
        for email in set(all_repo_owner):
            if email not in name_dict:
                if '@seafile_group' in email:
                    group_id = get_group_id_by_repo_owner(email)
                    group_name = group_id_to_name(group_id)
                    name_dict[email] = group_name
                else:
                    name_dict[email] = email2nickname(email)

        for repo in repos:
            repo_owner = repo_id_owner_dict[repo.id]
            repo.owner = repo_owner
            repo.owner_name = name_dict.get(repo.owner, '')

            if '@seafile_group' in repo_owner:
                repo.is_department_repo = True
                group_id = get_group_id_by_repo_owner(repo_owner)
                repo.group_id = group_id
            else:
                repo.is_department_repo = False
                repo.group_id = ''

    elif owner:     # search by owner
        repos = list_org_repos_by_owner(org_id, owner)
        for repo in repos:
            repo.owner_name = email2nickname(owner)
            repo.is_department_repo = False
            repo.group_id = ''

    return render(request, 'organizations/org_repo_search.html', {
            'repos': repos,
            'name': repo_name,
            'owner': owner,
            })

@login_required
@org_staff_required
def org_group_admin(request):
    """List orgnization groups.
    """
    org_id = request.user.org.org_id

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '25'))
    except ValueError:
        current_page = 1
        per_page = 25

    groups_plus_one = get_org_groups(org_id, per_page * (current_page -1),
                                     per_page +1)
    groups = groups_plus_one[:per_page]

    if len(groups_plus_one) == per_page + 1:
        page_next = True
    else:
        page_next = False

    return render(request, 'organizations/org_group_admin.html', {
            'groups': groups,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@org_staff_required
@require_POST
def org_group_remove(request, group_id):
    group_id = int(group_id)
    org = request.user.org

    # permission checking
    if get_org_id_by_group(group_id) != org.org_id:
        raise Http404

    try:
        remove_org_group(org.org_id, group_id, request.user.username)
    except SearpcError as e:
        logger.error(e)

    next = request.META.get('HTTP_REFERER', reverse('org_group_admin'))
    return HttpResponseRedirect(next)

@login_required
@org_staff_required
def org_user_info(request, email):
    if not is_valid_username(email):
        raise Http404

    org_id = request.user.org.org_id
    # check whether user belong to that org
    if not seaserv.org_user_exists(org_id, email):
        raise Http404

    owned_repos = seafile_api.get_org_owned_repo_list(org_id, email)
    owned_repos = filter(lambda r: not r.is_virtual, owned_repos)

    quota = get_org_user_quota(org_id, email)
    quota_usage = get_org_user_self_usage(org_id, email)

    # Repos that are share to user
    in_repos = seafile_api.get_org_share_in_repo_list(org_id, email, -1, -1)

    # get user profile
    profile = Profile.objects.get_profile_by_user(email)

    org_name = request.user.org.org_name

    return render(request, 'organizations/userinfo.html', {
            'owned_repos': owned_repos,
            'quota': quota,
            'quota_usage': quota_usage,
            'in_repos': in_repos,
            'email': email,
            'profile': profile,
            'org_id': org_id,
            'org_name': org_name,
            })

@login_required_ajax
@org_staff_required
@require_POST
def org_user_toggle_status(request, user_id):
    """Active or deactive a organization user.
    """
    content_type = 'application/json; charset=utf-8'
    org = request.user.org

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        return HttpResponse(json.dumps({'success': False}), status=400,
                            content_type=content_type)

    # permission checking
    if not org_user_exists(org.org_id, user.username):
        return HttpResponse(json.dumps({'success': False}), status=400,
                            content_type=content_type)

    try:
        user_status = int(request.POST.get('s', 0))
    except ValueError:
        user_status = 0

    user.is_active = bool(user_status)
    user.save()
    if user.is_active is True:
        try:
            email_user_on_activation(user)
            email_sent = True
        except Exception as e:
            logger.error(e)
            email_sent = False

        return HttpResponse(json.dumps({'success': True,
                                        'email_sent': email_sent,
                                        }), content_type=content_type)
    return HttpResponse(json.dumps({'success': True}),
                            content_type=content_type)

@login_required
@org_staff_required
def org_user_set_quota(request, email):
    if not request.is_ajax() or request.method != 'POST':
        raise Http404

    ct = 'application/json; charset=utf-8'
    result = {}

    if not is_valid_username(email):
        result['error'] = 'Failed to set quota: invalid email'
        return HttpResponse(json.dumps(result), status=400, content_type=ct)

    org_id = request.user.org.org_id
    # check whether user belong to that org
    if not seaserv.org_user_exists(org_id, email):
        raise Http404

    quota_mb = int(request.POST.get('quota', 0))
    quota = quota_mb * get_file_size_unit('mb')

    org_quota_mb = get_org_quota(org_id) / get_file_size_unit('mb')
    if quota_mb > org_quota_mb:
        result['error'] = _(u'Failed to set quota: maximum quota is %d MB' % \
                                org_quota_mb)
        return HttpResponse(json.dumps(result), status=400, content_type=ct)

    try:
        seaserv.seafserv_threaded_rpc.set_org_user_quota(org_id, email, quota)
    except SearpcError as e:
        logger.error(e)
        result['error'] = 'Failed to set quota: internal error'
        return HttpResponse(json.dumps(result), status=500, content_type=ct)

    result['success'] = True
    return HttpResponse(json.dumps(result), content_type=ct)

@login_required
@org_staff_required
def org_publink_admin(request):
    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    offset = per_page * (current_page -1)
    limit = per_page + 1
    org_id = request.user.org.org_id
    ofs = OrgFileShare.objects.filter(org_id=org_id)[offset:offset+limit]
    publinks = [ x.file_share for x in ofs ]

    if len(publinks) == per_page + 1:
        page_next = True
    else:
        page_next = False

    for l in publinks:
        if l.is_file_share_link():
            l.name = os.path.basename(l.path)
        else:
            l.name = os.path.dirname(l.path)

    return render(request, 'organizations/org_publink_admin.html', {
            'publinks': publinks,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
        })

@login_required
@org_staff_required
def org_publink_remove(request):
    # if request.method != 'POST':
    #     raise Http404

    token = request.GET.get('t')
    try:
        fs = FileShare.objects.get(token=token)
    except FileShare.DoesNotExist:
        raise Http404

    org_id = request.user.org.org_id
    if len(OrgFileShare.objects.filter(org_id=org_id, file_share=fs)) > 0:
        fs.delete()

    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = reverse('org_publink_admin')

    messages.success(request, _('Successfully deleted.'))
    return HttpResponseRedirect(next)

@login_required_ajax
@org_staff_required
def batch_org_user_make_admin(request):
    """Batch set urg users as organization admin."""

    if request.method != 'POST':
        raise Http404

    result = {}
    content_type = 'application/json; charset=utf-8'

    set_admin_emails = request.POST.get('set_admin_emails')
    set_admin_emails = string2list(set_admin_emails)

    # replace contact email with ccnet email if any
    set_admin_emails = convert_contact_emails(set_admin_emails)

    success = []
    failed = []
    already_admin = []

    user_name_map = {}
    for e in Profile.objects.filter(user__in=set_admin_emails):
        user_name_map[e.user] = e.nickname

    org = request.user.org
    for email in set_admin_emails:
        if org_user_exists(org.org_id, email):
            try:
                name = user_name_map[email]
            except KeyError:
                name = email

            if is_org_staff(org.org_id, email):
                already_admin.append(name)
            else:
                set_org_staff(org.org_id, email)
                success.append(name)
        else:
            failed.append(email)

    for item in success + already_admin:
        messages.success(request, _(u'Successfully set %s as admin.') % item)
    for item in failed:
        messages.error(request, _(u'Failed to set %s as admin: user does not exist.') % item)

    result['success'] = True
    return HttpResponse(json.dumps(result), content_type=content_type)

@login_required
@org_staff_required
def org_manage(request):
    """Management page for org admin.

    Arguments:
    - `request`:
    """
    org_id = request.user.org.org_id

    url_prefix = request.user.org.url_prefix

    # space quota
    try:
        storage_quota = get_org_quota(org_id)
    except Exception as e:
        logger.error(e)
        storage_quota = 0

    # storage usage
    try:
        storage_usage = seafile_api.get_org_quota_usage(org_id)
    except Exception as e:
        logger.error(e)
        storage_usage = 0

    # member quota
    if ORG_MEMBER_QUOTA_ENABLED:
        from seahub_extra.organizations.models import OrgMemberQuota
        member_quota = OrgMemberQuota.objects.get_quota(org_id)
    else:
        member_quota = None

    try:
        org_members = ccnet_api.get_org_users_by_url_prefix(url_prefix, -1, -1)
    except Exception as e:
        logger.error(e)
        org_members = []

    member_usage = 0
    active_member_usage = 0
    if org_members:
        # member usage
        member_usage = len(org_members)
        active_members = filter(lambda m: m.is_active, org_members)
        active_member_usage = len(active_members)

    return render(request, 'organizations/org_manage.html', {
        'storage_quota': storage_quota,
        'storage_usage': storage_usage,
        'member_quota': member_quota,
        'member_usage': member_usage,
        'active_member_usage': active_member_usage,
        'ORG_MEMBER_QUOTA_ENABLED': ORG_MEMBER_QUOTA_ENABLED,
    })

@login_required
@org_staff_required
def org_admin(request):
    """backbone pages for org admin.

    Arguments:
    - `request`:
    """
    return render(request, 'organizations/org_admin_backbone.html', {
    })

@login_required
@org_staff_required
def org_log_file_audit(request):
    """
    """
    if not EVENTS_ENABLED:
        raise Http404

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    user_selected = request.GET.get('email', None)
    repo_selected = request.GET.get('repo_id', None)

    start = per_page * (current_page - 1)
    limit = per_page

    org_id = request.user.org.org_id
    events = get_file_audit_events(user_selected, org_id, repo_selected, start, limit)

    if events:
        for ev in events:
            ev.repo = get_repo(ev.repo_id)
            ev.filename = os.path.basename(ev.file_path)
            ev.time = utc_to_local(ev.timestamp)
            if org_user_exists(org_id, ev.user):
                ev.is_org_user = True

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'organizations/org_file_audit.html', {
            'events': events,
            'user_selected': user_selected,
            'repo_selected': repo_selected,
            'extra_href': extra_href,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@org_staff_required
def org_log_file_update(request):
    """
    """
    if not EVENTS_ENABLED:
        raise Http404

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    user_selected = request.GET.get('email', None)
    repo_selected = request.GET.get('repo_id', None)

    start = per_page * (current_page - 1)
    limit = per_page

    org_id = request.user.org.org_id
    events = get_file_update_events(user_selected, org_id, repo_selected, start, limit)

    if events:
        for ev in events:
            ev.repo = get_repo(ev.repo_id)
            ev.local_time = utc_to_local(ev.timestamp)
            ev.time = int(ev.local_time.strftime('%s'))
            if org_user_exists(org_id, ev.user):
                ev.is_org_user = True

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'organizations/org_file_update.html', {
            'events': events,
            'user_selected': user_selected,
            'repo_selected': repo_selected,
            'extra_href': extra_href,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@org_staff_required
def org_log_perm_audit(request):
    """
    """
    if not EVENTS_ENABLED:
        raise Http404

    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    user_selected = request.GET.get('email', None)
    repo_selected = request.GET.get('repo_id', None)

    start = per_page * (current_page - 1)
    limit = per_page

    org_id = request.user.org.org_id
    events = get_perm_audit_events(user_selected, org_id, repo_selected, start, limit)

    if events:
        for ev in events:
            if ev.to.isdigit():
                ev.perm_group_name = get_group(ev.to).group_name if \
                    get_group(ev.to) is not None else None

            ev.repo = get_repo(ev.repo_id)
            ev.folder_name = os.path.basename(ev.file_path)
            ev.time = utc_to_local(ev.timestamp)

            if org_user_exists(org_id, ev.from_user):
                ev.is_org_from_user = True

            if org_user_exists(org_id, ev.to):
                ev.is_org_to_user = True

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'organizations/org_perm_audit.html', {
            'events': events,
            'user_selected': user_selected,
            'repo_selected': repo_selected,
            'extra_href': extra_href,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@org_staff_required
def org_admin_group_info(request, group_id):

    group_id = int(group_id)
    group = get_group(group_id)
    org_id = request.user.org.org_id
    repos = seafile_api.get_org_group_repos(org_id, group_id)
    members = get_group_members(group_id)

    return render(request, 'organizations/org_admin_group_info.html', {
            'group': group,
            'repos': repos,
            'members': members,
            })

@login_required
@org_staff_required
def react_fake_view(request, **kwargs):
    group_id = kwargs.get('group_id', '')
    org = request.user.org

    # Whether use new page
    return render(request, "organizations/org_admin_react.html", {
        'org': org,
        'org_member_quota_enabled': ORG_MEMBER_QUOTA_ENABLED,
        'group_id': group_id,
        })
