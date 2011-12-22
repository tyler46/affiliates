from django.conf import settings

from funfactory.urlresolvers import reverse
from mock import patch
from nose.tools import eq_, ok_

from banners.models import BannerInstance
from shared.tests import TestCase


@patch.object(settings, 'LANGUAGES', {'en-us': 'English (US)', 'fr': 'French'})
class CustomizeViewTests(TestCase):
    fixtures = ['banners']

    def setUp(self):
        self.browserid_login('testuser42@asdf.asdf')

    def _post(self, badge, image):
        with self.activate('en-US'):
            url = reverse('banners.customize', kwargs={'banner_pk': badge})
        return self.client.post(url, {'image': image})

    def test_create_instance(self):
        """Test that the view can successfully create a bannerinstance."""
        response = self._post(1, 2)
        eq_(response.status_code, 302)
        ok_(BannerInstance.objects.filter(user=1, badge=1, image=2).exists())

    def test_invalid_image_id(self):
        """
        Test that giving an invalid image ID does not attempt to create a
        new bannerinstance.
        """
        response = self._post(1, 999)
        eq_(response.status_code, 200)

        with self.assertRaises(BannerInstance.DoesNotExist):
            BannerInstance.objects.get(user=1, badge=1, image=999)


@patch.object(settings, 'DEFAULT_AFFILIATE_LINK', 'http://test.com')
class LinkViewTests(TestCase):
    fixtures = ['banners']

    def _get_link(self, instance_id):
        with self.activate('en-US'):
            url = reverse('banners.link',
                          kwargs={'banner_instance_id': instance_id})
        return self.client.get(url)

    def test_basic(self):
        """
        Test that the link view can increment clicks on an existing
        bannerinstance and redirects properly.
        """
        old_clicks = BannerInstance.objects.get(pk=2).clicks
        response = self._get_link(2)
        new_clicks = BannerInstance.objects.get(pk=2).clicks

        eq_(new_clicks, old_clicks + 1)
        eq_(response.status_code, 302)
        eq_(response['Location'], 'http://www.mozilla.org')

    def test_default_redirect(self):
        """Test default redirect on an invalid bannerinstance."""
        response = self._get_link(999)
        eq_(response['Location'], 'http://test.com')


@patch.object(settings, 'DEFAULT_AFFILIATE_LINK', 'http://test.com')
class OldLinkViewTests(TestCase):
    fixtures = ['banners']

    def _get_link(self, user_id, banner_id, img_id):
        kwargs = {'user_id': user_id, 'banner_id': banner_id,
                  'banner_img_id': img_id}
        with self.activate('en-US'):
            url = reverse('banners.link.old', kwargs=kwargs)
        return self.client.get(url)

    def test_basic(self):
        """
        Test that the old link view can increment clicks on an existing
        bannerinstance and redirects properly.
        """
        old_clicks = BannerInstance.objects.get(pk=2).clicks
        response = self._get_link(1, 1, 1)
        new_clicks = BannerInstance.objects.get(pk=2).clicks

        eq_(new_clicks, old_clicks + 1)
        eq_(response.status_code, 302)
        eq_(response['Location'], 'http://www.mozilla.org')

    def test_redirect_default_on_error(self):
        """
        Test that the link redirects to the default link if a banner cannot
        be found.
        """
        response = self._get_link(1, 999, 1)
        eq_(response['Location'], 'http://test.com')

    def test_does_not_create(self):
        """Test that the link does not create a new bannerinstance."""
        self._get_link(1, 1, 4)
        with self.assertRaises(BannerInstance.DoesNotExist):
            BannerInstance.objects.get(user__id=1, badge__id=1, image__id=4)
