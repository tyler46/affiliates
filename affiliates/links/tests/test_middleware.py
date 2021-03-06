from django.core.urlresolvers import Resolver404
from django.test.client import RequestFactory

from nose.tools import eq_, ok_
from mock import Mock, patch

from affiliates.base.tests import aware_date, aware_datetime, TestCase
from affiliates.facebook.tests import FacebookUserFactory
from affiliates.links.middleware import ReferralSkipMiddleware, StatsSinceLastVisitMiddleware
from affiliates.links.tests import DataPointFactory
from affiliates.users.models import UserProfile
from affiliates.users.tests import UserFactory


class StatsSinceLastVisitMiddlewareTests(TestCase):
    def setUp(self):
        self.middleware = StatsSinceLastVisitMiddleware()
        self.factory = RequestFactory()
        self.request = self.factory.get('/')

        messages_patch = patch('affiliates.links.middleware.messages')
        self.addCleanup(messages_patch.stop)
        self.messages = messages_patch.start()

    def test_process_request_unauthenticated(self):
        """
        If the current user isn't authed, return None and do not log a
        message.
        """
        self.request.user = Mock()
        self.request.user.is_authenticated.return_value = False

        eq_(self.middleware.process_request(self.request), None)
        ok_(not self.messages.info.called)

    def test_process_request_facebook_user(self):
        """
        If the current user doesn't have a profile (either as a
        FacebookUser or no profile in the database) return None and do
        not log a message.
        """
        self.request.user = FacebookUserFactory.create()
        eq_(self.middleware.process_request(self.request), None)
        ok_(not self.messages.info.called)

        self.request.user = UserFactory.create(userprofile=None)
        eq_(self.middleware.process_request(self.request), None)
        ok_(not self.messages.info.called)

    def test_process_request_no_last_visit(self):
        """
        If we haven't logged a last visit for the user, set their
        last_visit and return None and do not log a message.
        """
        self.request.user = UserFactory.create(userprofile__last_visit=None)

        with patch('affiliates.links.middleware.timezone.now') as mock_now:
            mock_now.return_value = aware_datetime(2014, 1, 1)
            eq_(self.middleware.process_request(self.request), None)
            ok_(not self.messages.info.called)

        profile = UserProfile.objects.get(user=self.request.user)
        eq_(profile.last_visit, aware_date(2014, 1, 1))

    def test_process_request_less_than_one_day(self):
        """
        If it has been less than one day since the user's last visit,
        return None and do not log a message.
        """
        self.request.user = UserFactory.create(userprofile__last_visit=aware_date(2014, 1, 1))

        with patch('affiliates.links.middleware.timezone.now') as mock_now:
            mock_now.return_value = aware_datetime(2014, 1, 1)
            eq_(self.middleware.process_request(self.request), None)
            ok_(not self.messages.info.called)

    def test_process_request_no_clicks_or_downloads(self):
        """
        If there were no clicks or downloads since the user's last
        visit, update their last_visit date and do not log a message.
        """
        self.request.user = UserFactory.create(userprofile__last_visit=aware_date(2014, 1, 1))

        with patch('affiliates.links.middleware.timezone.now') as mock_now:
            mock_now.return_value = aware_datetime(2014, 1, 3)
            eq_(self.middleware.process_request(self.request), None)
            ok_(not self.messages.info.called)

        profile = UserProfile.objects.get(user=self.request.user)
        eq_(profile.last_visit, aware_date(2014, 1, 3))

    def test_process_request_clicks_and_downloads(self):
        """
        If there were any clicks or downloads since the user's last
        visit, update their last_visit date and log a message.
        """
        self.request.user = UserFactory.create(userprofile__last_visit=aware_date(2014, 1, 1))

        # Date of last visit not included.
        DataPointFactory.create(link__user=self.request.user, date=aware_date(2014, 1, 1),
                                link_clicks=3, firefox_downloads=9)

        # Current date and dates between are included.
        DataPointFactory.create(link__user=self.request.user, date=aware_date(2014, 1, 2),
                                link_clicks=4, firefox_downloads=7)
        DataPointFactory.create(link__user=self.request.user, date=aware_date(2014, 1, 3),
                                link_clicks=1, firefox_downloads=2)

        with patch('affiliates.links.middleware.timezone.now') as mock_now:
            mock_now.return_value = aware_datetime(2014, 1, 3)
            eq_(self.middleware.process_request(self.request), None)
            ok_(self.messages.info.called)

        message = self.messages.info.call_args[0][1]
        ok_('5' in message and '9' in message)

        profile = UserProfile.objects.get(user=self.request.user)
        eq_(profile.last_visit, aware_date(2014, 1, 3))


class ReferralSkipMiddlewareTests(TestCase):
    def setUp(self):
        self.middleware = ReferralSkipMiddleware()
        self.factory = RequestFactory()

    def test_process_request_resolver404(self):
        """If resolve raises a Resolver404 error, return None."""
        request = self.factory.get('/')

        with patch('affiliates.links.middleware.resolve') as resolve:
            resolve.side_effect = Resolver404
            eq_(self.middleware.process_request(request), None)
            resolve.assert_called_with('/')

    def test_process_request_viewname_mismatch(self):
        """
        If the resolved view name isn't in self.view_names, return None.
        """
        request = self.factory.get('/foo')
        self.middleware.view_names = ('bears', 'bears', 'bears')

        with patch('affiliates.links.middleware.resolve') as resolve:
            resolve.return_value.view_name = 'my.view'
            eq_(self.middleware.process_request(request), None)
            resolve.assert_called_with('/foo')

    def test_process_request_viewname_match(self):
        """
        If the resolved view name is in self.view_names, execute the
        view function with the given args and kwargs.
        """
        request = self.factory.get('/bar')
        self.middleware.view_names = ('kakumei', 'dualism')

        with patch('affiliates.links.middleware.resolve') as resolve:
            match = Mock(view_name='kakumei', args=[1, 'valvrave'],
                         kwargs={'haruto': 'l-elf', 'saki': 4})
            resolve.return_value = match

            eq_(self.middleware.process_request(request), match.func.return_value)
            resolve.assert_called_with('/bar')
            match.func.assert_called_with(request, 1, 'valvrave', haruto='l-elf', saki=4)
