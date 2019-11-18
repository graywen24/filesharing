# Copyright (c) 2012-2016 Seafile Ltd.
import os
import logging

from django.shortcuts import render

from django.utils.translation import ugettext as _
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.exceptions import ValidationError
from post_office.models import Email, Log

from seahub.api2.endpoints.utils import check_time_period_valid, \
    get_log_events_by_type_and_time

from seahub.base.decorators import sys_staff_required
from seahub.auth.decorators import login_required
from seahub_extra.sysadmin_extra.models import UserLoginLog
from seahub.utils import EVENTS_ENABLED, get_file_audit_events, \
    get_file_update_events, get_perm_audit_events, \
    is_pro_version, generate_file_audit_event_type
from seahub.utils.timeutils import utc_to_local
from seahub.utils.ms_excel import write_xls
from seahub.settings import SITE_ROOT

from seaserv import seafile_api, ccnet_api

logger = logging.getLogger(__name__)

@login_required
@sys_staff_required
def sys_login_admin(request):
    """
    """
    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    offset = per_page * (current_page - 1)
    limit = per_page + 1
    logs_plus_one = list(UserLoginLog.objects.all()[offset:offset + limit])
    logs = logs_plus_one[:per_page]
    page_next = True if len(logs_plus_one) == per_page + 1 else False

    return render(request, 'sys_login_admin.html', {
            'logs': logs,
            'current_page': current_page,
            'prev_page': current_page-1,
            'next_page': current_page+1,
            'per_page': per_page,
            'page_next': page_next,
            })

@login_required
@sys_staff_required
def sys_login_admin_export_excel(request):
    """ Export user login logs to excel.
    """
    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = SITE_ROOT

    start = request.GET.get('start', None)
    end = request.GET.get('end', None)

    if not check_time_period_valid(start, end):
        messages.error(request, _(u'Failed to export excel, invalid start or end date'))
        return HttpResponseRedirect(next)

    # Filtering a DateTimeField with dates won't include items on the last day,
    # because the bounds are interpreted as '0am on the given date'.
    end = end + ' 23:59:59'

    try:
        user_login_logs = UserLoginLog.objects.filter(login_date__range=(start, end))
    except ValidationError as e:
        logger.error(e)
        messages.error(request, _(u'Failed to export excel, invalid start or end date'))
        return HttpResponseRedirect(next)

    logs = list(user_login_logs)
    head = [_("Name"), _("IP"), _("Status"), _("Time"),]
    data_list = []
    for log in logs:
        login_time = log.login_date.strftime("%Y-%m-%d %H:%M:%S")
        status = _('Success') if log.login_success else _('Failed')
        row = [log.username, log.login_ip, status, login_time,]
        data_list.append(row)

    wb = write_xls(_('login-logs'), head, data_list)
    if not wb:
        messages.error(request, _(u'Failed to export excel'))
        return HttpResponseRedirect(next)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=login-logs.xlsx'
    wb.save(response)
    return response

@login_required
@sys_staff_required
def sys_log_file_audit(request):
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

    # org_id = 0, show all file audit
    events = get_file_audit_events(user_selected, 0, repo_selected, start, limit)

    if events:
        for ev in events:
            repo_id = ev.repo_id
            repo = seafile_api.get_repo(repo_id)
            if repo:
                ev.repo_name = repo.name
                ev.repo_owner = seafile_api.get_repo_owner(repo_id) or \
                        seafile_api.get_org_repo_owner(repo_id)
            else:
                ev.repo_name = _('Deleted')
                ev.repo_owner = '--'

            if ev.file_path.endswith('/'):
                ev.file_or_dir_name = '/' if ev.file_path == '/' else os.path.basename(ev.file_path.rstrip('/'))
            else:
                ev.file_or_dir_name = os.path.basename(ev.file_path)

            ev.time = utc_to_local(ev.timestamp)
            ev.event_type, ev.show_device = generate_file_audit_event_type(ev)

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'sys_file_audit.html', {
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
@sys_staff_required
def sys_log_file_audit_export_excel(request):
    """ Export file access logs to excel.
    """
    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = SITE_ROOT

    if not is_pro_version():
        messages.error(request, _(u'Failed to export excel, this feature is only in professional version.'))
        return HttpResponseRedirect(next)

    start = request.GET.get('start', None)
    end = request.GET.get('end', None)
    if not check_time_period_valid(start, end):
        messages.error(request, _(u'Failed to export excel, invalid start or end date'))
        return HttpResponseRedirect(next)

    events = get_log_events_by_type_and_time('file_audit', start, end)

    head = [_("User"), _("Type"), _("IP"), _("Device"), _("Date"),
            _("Library Name"), _("Library ID"), _("Library Owner"), _("File Path"),]
    data_list = []

    events.sort(lambda x, y: cmp(y.timestamp, x.timestamp))
    for ev in events:
        event_type, ev.show_device = generate_file_audit_event_type(ev)

        repo_id = ev.repo_id
        repo = seafile_api.get_repo(repo_id)
        if repo:
            repo_name = repo.name
            repo_owner = seafile_api.get_repo_owner(repo_id) or \
                    seafile_api.get_org_repo_owner(repo_id)
        else:
            repo_name = _('Deleted')
            repo_owner = '--'

        username = ev.user if ev.user else _('Anonymous User')
        date = utc_to_local(ev.timestamp).strftime('%Y-%m-%d %H:%M:%S') if \
            ev.timestamp else ''

        row = [username, event_type, ev.ip, ev.show_device,
               date, repo_name, ev.repo_id, repo_owner, ev.file_path]
        data_list.append(row)

    wb = write_xls(_('file-access-logs'), head, data_list)
    if not wb:
        messages.error(request, _(u'Failed to export excel'))
        return HttpResponseRedirect(next)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=file-access-logs.xlsx'
    wb.save(response)
    return response

@login_required
@sys_staff_required
def sys_log_file_update(request):
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

    # org_id = 0, show all file audit
    events = get_file_update_events(user_selected, 0, repo_selected, start, limit)

    if events:
        for ev in events:
            repo_id = ev.repo_id
            repo = seafile_api.get_repo(repo_id)
            if repo:
                ev.repo = repo
                ev.repo_name = repo.name
                ev.repo_owner = seafile_api.get_repo_owner(repo_id) or \
                        seafile_api.get_org_repo_owner(repo_id)
                ev.repo_encrypted = repo.encrypted
            else:
                ev.repo_name = _('Deleted')
                ev.repo_owner = '--'

            ev.local_time = utc_to_local(ev.timestamp)
            ev.time = int(ev.local_time.strftime('%s'))

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'sys_file_update.html', {
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
@sys_staff_required
def sys_log_file_update_export_excel(request):
    """ Export file update logs to excel.
    """
    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = SITE_ROOT

    if not is_pro_version():
        messages.error(request, _(u'Failed to export excel, this feature is only in professional version.'))
        return HttpResponseRedirect(next)

    start = request.GET.get('start', None)
    end = request.GET.get('end', None)
    if not check_time_period_valid(start, end):
        messages.error(request, _(u'Failed to export excel, invalid start or end date'))
        return HttpResponseRedirect(next)

    events = get_log_events_by_type_and_time('file_update', start, end)

    head = [_("User"), _("Date"), _("Library Name"), _("Library ID"),
            _("Library Owner"), _("Action"),]
    data_list = []

    events.sort(lambda x, y: cmp(y.timestamp, x.timestamp))
    for ev in events:

        repo_id = ev.repo_id
        repo = seafile_api.get_repo(repo_id)
        if repo:
            repo_name = repo.name
            repo_owner = seafile_api.get_repo_owner(repo_id) or \
                    seafile_api.get_org_repo_owner(repo_id)
        else:
            repo_name = _('Deleted')
            repo_owner = '--'

        username = ev.user if ev.user else _('Anonymous User')
        date = utc_to_local(ev.timestamp).strftime('%Y-%m-%d %H:%M:%S') if \
            ev.timestamp else ''

        row = [username, date, repo_name, ev.repo_id, repo_owner, ev.file_oper.strip(),]
        data_list.append(row)

    wb = write_xls(_('file-update-logs'), head, data_list)
    if not wb:
        messages.error(request, _(u'Failed to export excel'))
        return HttpResponseRedirect(next)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=file-update-logs.xlsx'
    wb.save(response)
    return response

@login_required
@sys_staff_required
def sys_log_perm_audit(request):
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

    # org_id = 0, show all file audit
    events = get_perm_audit_events(user_selected, 0, repo_selected, start, limit)

    if events:
        for ev in events:
            if ev.to.isdigit():
                group = ccnet_api.get_group(int(ev.to))
                ev.perm_group_name = group.group_name if group else None

            ev.repo = seafile_api.get_repo(ev.repo_id)
            ev.folder_name = os.path.basename(ev.file_path)
            ev.time = utc_to_local(ev.timestamp)

        page_next = True if len(events) == per_page else False

    else:
        page_next = False

    extra_href = ''
    if user_selected:
        extra_href += "&email=%s" % user_selected

    if repo_selected:
        extra_href += "&repo_id=%s" % repo_selected

    return render(request, 'sys_perm_audit.html', {
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
@sys_staff_required
def sys_log_perm_audit_export_excel(request):
    """ Export permission audit logs to excel.
    """
    next = request.META.get('HTTP_REFERER', None)
    if not next:
        next = SITE_ROOT

    if not is_pro_version():
        messages.error(request, _(u'Failed to export excel, this feature is only in professional version.'))
        return HttpResponseRedirect(next)

    start = request.GET.get('start', None)
    end = request.GET.get('end', None)
    if not check_time_period_valid(start, end):
        messages.error(request, _(u'Failed to export excel, invalid start or end date'))
        return HttpResponseRedirect(next)

    events = get_log_events_by_type_and_time('perm_audit', start, end)

    head = [_("From"), _("To"), _("Action"), _("Permission"), _("Library"),
            _("Folder Path"), _("Date"),]
    data_list = []

    events.sort(lambda x, y: cmp(y.timestamp, x.timestamp))
    for ev in events:
        repo = seafile_api.get_repo(ev.repo_id)
        repo_name = repo.repo_name if repo else _('Deleted')

        if '@' in ev.to:
            to = ev.to
        elif ev.to.isdigit():
            group = ccnet_api.get_group(int(ev.to))
            to = group.group_name if group else _('Deleted')
        elif 'all' in ev.to:
            to = _('Organization')
        else:
            to = '--'

        if 'add' in ev.etype:
            action = _('Add')
        elif 'modify' in ev.etype:
            action = _('Modify')
        elif 'delete' in ev.etype:
            action = _('Delete')
        else:
            action = '--'

        if ev.permission == 'rw':
            permission = _('Read-Write')
        elif ev.permission == 'r':
            permission = _('Read-Only')
        else:
            permission = '--'

        date = utc_to_local(ev.timestamp).strftime('%Y-%m-%d %H:%M:%S') if \
            ev.timestamp else ''

        row = [ev.from_user, to, action, permission, repo_name,
               ev.file_path, date,]
        data_list.append(row)

    wb = write_xls(_('perm-audit-logs'), head, data_list)
    if not wb:
        next = request.META.get('HTTP_REFERER', None)
        if not next:
            next = SITE_ROOT

        messages.error(request, _(u'Failed to export excel'))
        return HttpResponseRedirect(next)

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=perm-audit-logs.xlsx'
    wb.save(response)
    return response

@login_required
@sys_staff_required
def sys_log_email_audit(request):
    # Make sure page request is an int. If not, deliver first page.
    try:
        current_page = int(request.GET.get('page', '1'))
        per_page = int(request.GET.get('per_page', '100'))
    except ValueError:
        current_page = 1
        per_page = 100

    offset = per_page * (current_page - 1)
    limit = per_page + 1
    emails_plus_one = list(Email.objects.all().order_by('-created')[offset:offset + limit])
    page_next = True if len(emails_plus_one) == per_page + 1 else False

    emails = emails_plus_one[:per_page]
    for e in emails:
        e.to_str = ", ".join(e.to)
        e.priority_str = e.PRIORITY_CHOICES[e.priority][1]
        if e.status is None:
            e.status_str = 'sending'
        else:
            e.status_str = e.STATUS_CHOICES[e.status][1]

        if e.status == 0:       # success
            e.success = True

        if e.status == 1:       # failed
            e.failed = True
            e.error_msg = Log.objects.get(email=e).message

    return render(request, 'sys_log_email_audit.html', {
            'emails': emails,
            'current_page': current_page,
            'prev_page': current_page - 1,
            'next_page': current_page + 1,
            'per_page': per_page,
            'page_next': page_next,
    })
