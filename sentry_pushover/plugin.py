# -*- coding: utf-8 -*-

'''
Sentry-Pushover
=============

License
-------
Copyright 2012 Janez Troha

This file is part of Sentry-Pushover.

Sentry-Pushover is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Sentry-Pushover is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Sentry-Pushover.  If not, see <http://www.gnu.org/licenses/>.
'''
import logging
import requests
import sentry_pushover
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from sentry.plugins import Plugin
from sentry.utils.safe import safe_execute


class PushoverSettingsForm(forms.Form):

    userkey = forms.CharField(help_text=_('Your user key. See https://pushover.net/'))
    apikey = forms.CharField(help_text=_('Application API token. See https://pushover.net/apps/'))

    choices = ((logging.CRITICAL, 'CRITICAL'), (logging.ERROR, 'ERROR'), (logging.WARNING,
               'WARNING'), (logging.INFO, 'INFO'), (logging.DEBUG, 'DEBUG'))
    severity = forms.ChoiceField(choices=choices,
                                 help_text=_("Don't send notifications for events below this level."))

    priority = \
        forms.BooleanField(required=False,
                           help_text=_('High-priority notifications, also bypasses quiet hours.'))


class PushoverNotifications(Plugin):

    author = 'Janez Troha'
    author_url = 'http://dz0ny.info'
    title = 'Pushover'
    description = "Integrates Pushover notification"

    title = _('Pushover')
    conf_title = title
    conf_key = 'pushover'
    slug = 'pushover'

    resource_links = [
        ('Bug Tracker', 'https://github.com/dz0ny/sentry-pushover/issues'),
        ('Source', 'https://github.com/dz0ny/sentry-pushover'),
    ]

    version = sentry_pushover.VERSION
    project_conf_form = PushoverSettingsForm
    logger = logging.getLogger('sentry.plugins.pushover')

    def can_enable_for_projects(self):
        return True

    def is_setup(self, project):
        return all(self.get_option(key, project) for key in ('userkey', 'apikey'))

    def post_process(
        self,
        group,
        event,
        is_new,
        is_sample,
        **kwargs
        ):

        if not is_new or not self.is_setup(event.project):
            return

        # https://github.com/getsentry/sentry/blob/master/src/sentry/models.py#L353
        if event.level < int(self.get_option('severity', event.project)):
            return

        title = '%s: %s' % (event.get_level_display().upper(), event.error().split('\n')[0])

        link = '%s/%s/group/%d/' % (settings.URL_PREFIX, group.project.slug, group.id)

        message = '%s: %s\n' % (_('Server'), event.server_name)
        message += '%s: %s\n' % (_('Group'), event.group)
        message += '%s: %s\n' % (_('Logger'), event.logger)
        message += '%s: %s\n' % (_('Message'), event.message)

        safe_execute(self.send_notification, message, link, event)

    def send_notification(
        self,
        title,
        message,
        link,
        event,
        ):

        # see https://pushover.net/api
        priority = 0
        if self.get_option('priority', event.project):
            priority = 1
        params = {
            'user': self.get_option('userkey', event.project),
            'token': self.get_option('apikey', event.project),
            'message': message,
            'title': title,
            'url': link,
            'url_title': 'More info',
            'priority': priority,
        }
        res = requests.post('https://api.pushover.net/1/messages.json', params=params)
        if not res.ok:
            self.logger.error('Error happend when send message to Pushover, status code: %i' % res.status_code)
        else:
            if res.json().get('status', 0) != 1:
                self.logger.error('Notification failed to be sent to Pushover')
            else:
                self.logger.info('Notification sent to Pushover successfully')
