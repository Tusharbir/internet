import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .models import Category, Favorite, Item, ItemImage, Message, Report, User


def _tiny_gif():
    """Return a minimal valid GIF file for testing image uploads."""
    return (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00'
        b'\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21'
        b'\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44'
        b'\x01\x00\x3b'
    )


MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@uwindsor.ca'
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')

    def test_user_str(self):
        self.user.first_name = 'John'
        self.user.last_name = 'Doe'
        self.user.save()
        self.assertEqual(str(self.user), 'John Doe')

    def test_category_str(self):
        self.assertEqual(str(self.category), 'Electronics')

    def test_item_creation(self):
        item = Item.objects.create(
            seller=self.user, category=self.category,
            title='Test Laptop', description='A great laptop for testing' * 2,
            price=Decimal('299.99'), condition=Item.CONDITION_GOOD,
        )
        self.assertEqual(str(item), 'Test Laptop')
        self.assertEqual(item.status, Item.STATUS_PUBLISHED)
        self.assertEqual(item.location, 'UWindsor Campus')

    def test_item_image_creation(self):
        item = Item.objects.create(
            seller=self.user, category=self.category,
            title='Test Item', description='Description for testing images',
            price=Decimal('50.00'), condition=Item.CONDITION_NEW,
        )
        img = ItemImage.objects.create(
            item=item,
            image=SimpleUploadedFile('test.gif', _tiny_gif(), content_type='image/gif'),
        )
        self.assertIn('items/', img.image.name)

    def test_favorite_unique(self):
        item = Item.objects.create(
            seller=self.user, category=self.category,
            title='Fav Test', description='A description for fav testing',
            price=Decimal('10.00'), condition=Item.CONDITION_GOOD,
        )
        Favorite.objects.create(user=self.user, item=item)
        with self.assertRaises(Exception):
            Favorite.objects.create(user=self.user, item=item)

    def test_report_unique(self):
        other = User.objects.create_user(username='reporter', password='pass1234')
        item = Item.objects.create(
            seller=self.user, category=self.category,
            title='Report Test', description='A description for report testing',
            price=Decimal('10.00'), condition=Item.CONDITION_GOOD,
        )
        Report.objects.create(item=item, reporter=other, reason=Report.REASON_SPAM)
        with self.assertRaises(Exception):
            Report.objects.create(item=item, reporter=other, reason=Report.REASON_FRAUD)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AuthViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_page_loads(self):
        response = self.client.get(reverse('marketplace:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create account')

    def test_register_creates_user(self):
        response = self.client.post(reverse('marketplace:register'), {
            'username': 'newuser',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'new@uwindsor.ca',
            'university_email': 'new@uwindsor.ca',
            'password1': 'Str0ngP@ss!',
            'password2': 'Str0ngP@ss!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertIn('_auth_user_id', self.client.session)

    def test_register_duplicate_username_shows_field_error(self):
        User.objects.create_user(username='takenuser', password='testpass123')

        response = self.client.post(reverse('marketplace:register'), {
            'username': 'takenuser',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'taken@example.com',
            'university_email': 'taken@uwindsor.ca',
            'password1': 'Str0ngP@ss!',
            'password2': 'Str0ngP@ss!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A user with that username already exists.')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome back')

    def test_login_works(self):
        User.objects.create_user(username='loginuser', password='testpass123')
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_is_redirected_away_from_register(self):
        user = User.objects.create_user(username='member', password='testpass123')
        self.client.force_login(user)

        response = self.client.get(reverse('marketplace:register'))

        self.assertRedirects(response, reverse('marketplace:browse'))

    def test_staff_login_redirects_to_admin_panel(self):
        User.objects.create_user(username='staffer', password='testpass123', is_staff=True)

        response = self.client.post(reverse('login'), {
            'username': 'staffer',
            'password': 'testpass123',
        })

        self.assertRedirects(response, reverse('marketplace:admin_dashboard'))

    def test_logout_works_via_post(self):
        user = User.objects.create_user(username='logoutuser', password='testpass123')
        self.client.force_login(user)

        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('marketplace:landing'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset your password')

    def test_logged_in_navbar_shows_profile_link(self):
        user = User.objects.create_user(username='profileowner', password='testpass123')
        self.client.force_login(user)

        response = self.client.get(reverse('marketplace:browse'))

        self.assertContains(response, reverse('marketplace:profile'))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='member',
            password='testpass123',
            email='member@uwindsor.ca',
            university_email='member@uwindsor.ca',
            first_name='Member',
            last_name='User',
            student_id='00112233',
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse('marketplace:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_profile_page_loads_for_logged_in_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('marketplace:profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Profile')
        self.assertContains(response, 'member@uwindsor.ca')
        self.assertContains(response, '00112233')

    def test_profile_edit_updates_user_details(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('marketplace:profile_edit'), {
            'first_name': 'Kunal',
            'last_name': 'Rastogi',
            'email': 'kunal@uwindsor.ca',
            'university_email': 'kunal@uwindsor.ca',
            'student_id': '99887766',
        })

        self.assertRedirects(response, reverse('marketplace:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Kunal')
        self.assertEqual(self.user.last_name, 'Rastogi')
        self.assertEqual(self.user.email, 'kunal@uwindsor.ca')
        self.assertEqual(self.user.university_email, 'kunal@uwindsor.ca')
        self.assertEqual(self.user.student_id, '99887766')

    def test_profile_edit_rejects_non_uwindsor_university_email(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('marketplace:profile_edit'), {
            'first_name': 'Member',
            'last_name': 'User',
            'email': 'member@example.com',
            'university_email': 'member@example.com',
            'student_id': '00112233',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please use your @uwindsor.ca email address.')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class LandingViewTests(TestCase):
    def test_landing_loads(self):
        response = self.client.get(reverse('marketplace:landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UniTrade')

    def test_landing_has_categories(self):
        Category.objects.create(name='Books', slug='books')
        response = self.client.get(reverse('marketplace:landing'))
        self.assertContains(response, 'Books')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BrowseViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Books', slug='books')
        for i in range(12):
            Item.objects.create(
                seller=self.user, category=self.cat,
                title=f'Book {i}', description=f'Description for book number {i}',
                price=Decimal(f'{10 + i}.00'), condition=Item.CONDITION_GOOD,
            )

    def test_browse_loads(self):
        response = self.client.get(reverse('marketplace:browse'))
        self.assertEqual(response.status_code, 200)

    def test_browse_paginates(self):
        response = self.client.get(reverse('marketplace:browse'))
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['items']), 9)

    def test_browse_search(self):
        response = self.client.get(reverse('marketplace:browse'), {'q': 'Book 1'})
        self.assertEqual(response.status_code, 200)

    def test_browse_filter_category(self):
        response = self.client.get(reverse('marketplace:browse'), {'category': self.cat.pk})
        self.assertEqual(response.status_code, 200)
        for item in response.context['items']:
            self.assertEqual(item.category, self.cat)

    def test_browse_filter_price(self):
        response = self.client.get(reverse('marketplace:browse'), {'min_price': '15', 'max_price': '18'})
        self.assertEqual(response.status_code, 200)
        for item in response.context['items']:
            self.assertGreaterEqual(item.price, Decimal('15'))
            self.assertLessEqual(item.price, Decimal('18'))

    def test_browse_sort_price_low(self):
        response = self.client.get(reverse('marketplace:browse'), {'sort': 'price_low'})
        items = list(response.context['items'])
        prices = [i.price for i in items]
        self.assertEqual(prices, sorted(prices))

    def test_browse_sort_price_high(self):
        response = self.client.get(reverse('marketplace:browse'), {'sort': 'price_high'})
        items = list(response.context['items'])
        prices = [i.price for i in items]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_draft_items_not_in_browse(self):
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Draft Book', description='This is a draft item description',
            price=Decimal('5.00'), condition=Item.CONDITION_NEW,
            status=Item.STATUS_DRAFT,
        )
        response = self.client.get(reverse('marketplace:browse'))
        titles = [i.title for i in response.context['items']]
        self.assertNotIn('Draft Book', titles)

    def test_pagination_preserves_filters(self):
        response = self.client.get(reverse('marketplace:browse'), {'q': 'Book', 'page': '1'})
        self.assertIn('filter_params', response.context)

    def test_browse_shows_placeholder_for_listing_without_image(self):
        response = self.client.get(reverse('marketplace:browse'))
        self.assertContains(response, 'No image uploaded')
        self.assertContains(response, 'listing-media-placeholder')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ItemDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.user, category=self.cat,
            title='Detail Test', description='A long description for testing details',
            price=Decimal('50.00'), condition=Item.CONDITION_GOOD,
        )

    def test_detail_loads(self):
        response = self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Test')

    def test_draft_item_hidden_from_non_owner(self):
        self.item.status = Item.STATUS_DRAFT
        self.item.save()
        response = self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)

    def test_draft_visible_to_owner(self):
        self.item.status = Item.STATUS_DRAFT
        self.item.save()
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)

    def test_recently_viewed_session(self):
        self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        session = self.client.session
        self.assertIn(self.item.pk, session['recently_viewed_items'])

    def test_visit_history_tracked(self):
        self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        session = self.client.session
        self.assertIn('visit_history', session)

    def test_last_viewed_cookie(self):
        response = self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.cookies['last_viewed_item'].value, str(self.item.pk))

    def test_detail_shows_placeholder_when_listing_has_no_image(self):
        response = self.client.get(reverse('marketplace:item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No listing image uploaded')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ItemCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.client.login(username='seller', password='testpass123')

    def test_create_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('marketplace:item_post'))
        self.assertEqual(response.status_code, 302)

    def test_create_page_loads(self):
        response = self.client.get(reverse('marketplace:item_post'))
        self.assertEqual(response.status_code, 200)

    def test_create_item_with_image(self):
        img = SimpleUploadedFile('test.gif', _tiny_gif(), content_type='image/gif')
        response = self.client.post(reverse('marketplace:item_post'), {
            'title': 'New Laptop for Sale',
            'description': 'A great laptop for students at UWindsor',
            'price': '299.99',
            'condition': Item.CONDITION_GOOD,
            'category': self.cat.pk,
            'location': 'UWindsor Campus',
            'status': Item.STATUS_PUBLISHED,
            'images': img,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Item.objects.filter(title='New Laptop for Sale').exists())
        item = Item.objects.get(title='New Laptop for Sale')
        self.assertEqual(item.seller, self.user)
        self.assertEqual(item.images.count(), 1)

    def test_create_item_as_draft(self):
        img = SimpleUploadedFile('test.gif', _tiny_gif(), content_type='image/gif')
        response = self.client.post(reverse('marketplace:item_post'), {
            'title': 'Draft Laptop Item',
            'description': 'This laptop is saved as a draft listing',
            'price': '199.99',
            'condition': Item.CONDITION_LIKE_NEW,
            'category': self.cat.pk,
            'status': Item.STATUS_DRAFT,
            'images': img,
        })
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(title='Draft Laptop Item')
        self.assertEqual(item.status, Item.STATUS_DRAFT)

    def test_create_item_without_image_fails(self):
        response = self.client.post(reverse('marketplace:item_post'), {
            'title': 'No Image Item Here',
            'description': 'This item has no image and should fail',
            'price': '50.00',
            'condition': Item.CONDITION_GOOD,
            'category': self.cat.pk,
            'status': Item.STATUS_PUBLISHED,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Item.objects.filter(title='No Image Item Here').exists())

    def test_create_item_negative_price_fails(self):
        img = SimpleUploadedFile('test.gif', _tiny_gif(), content_type='image/gif')
        response = self.client.post(reverse('marketplace:item_post'), {
            'title': 'Negative Price Item',
            'description': 'This item should fail because the price is below zero.',
            'price': '-1.00',
            'condition': Item.CONDITION_GOOD,
            'category': self.cat.pk,
            'status': Item.STATUS_PUBLISHED,
            'images': img,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price must be zero or greater.')
        self.assertFalse(Item.objects.filter(title='Negative Price Item').exists())

    def test_create_item_invalid_extension_fails(self):
        fake_image = SimpleUploadedFile('notes.txt', b'not an image', content_type='image/png')
        response = self.client.post(reverse('marketplace:item_post'), {
            'title': 'Invalid Extension Item',
            'description': 'This item uses a bad extension and should be rejected cleanly.',
            'price': '20.00',
            'condition': Item.CONDITION_GOOD,
            'category': self.cat.pk,
            'status': Item.STATUS_PUBLISHED,
            'images': fake_image,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'unsupported file extension')
        self.assertFalse(Item.objects.filter(title='Invalid Extension Item').exists())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ItemUpdateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.other = User.objects.create_user(username='other', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.user, category=self.cat,
            title='Edit Me Item', description='This item will be edited in tests',
            price=Decimal('100.00'), condition=Item.CONDITION_NEW,
        )
        ItemImage.objects.create(
            item=self.item,
            image=SimpleUploadedFile('test.gif', _tiny_gif(), content_type='image/gif'),
        )

    def test_edit_page_loads_for_owner(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('marketplace:item_update', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('existing_images', response.context)

    def test_edit_forbidden_for_non_owner(self):
        self.client.login(username='other', password='testpass123')
        response = self.client.get(reverse('marketplace:item_update', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 403)

    def test_update_item(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.post(reverse('marketplace:item_update', kwargs={'pk': self.item.pk}), {
            'title': 'Updated Item Title',
            'description': 'Updated description for the test item',
            'price': '150.00',
            'condition': Item.CONDITION_LIKE_NEW,
            'category': self.cat.pk,
            'location': 'UWindsor Library',
            'status': Item.STATUS_PUBLISHED,
        })
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Updated Item Title')
        self.assertEqual(self.item.price, Decimal('150.00'))

    def test_update_rejects_invalid_delete_image_ids(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.post(reverse('marketplace:item_update', kwargs={'pk': self.item.pk}), {
            'title': 'Edit Me Item',
            'description': 'This item will be edited in tests with invalid image ids.',
            'price': '100.00',
            'condition': Item.CONDITION_NEW,
            'category': self.cat.pk,
            'location': 'UWindsor Campus',
            'status': Item.STATUS_PUBLISHED,
            'delete_images': 'abc',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'One or more selected images could not be removed.')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ItemDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.user, category=self.cat,
            title='Delete Me', description='This item will be deleted in tests',
            price=Decimal('25.00'), condition=Item.CONDITION_FAIR,
        )

    def test_delete_requires_owner(self):
        other = User.objects.create_user(username='other', password='testpass123')
        self.client.login(username='other', password='testpass123')
        response = self.client.post(reverse('marketplace:item_delete', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 403)

    def test_delete_success(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.post(reverse('marketplace:item_delete', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MarkSoldViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.user, category=self.cat,
            title='Sell Me', description='This item is ready to be sold',
            price=Decimal('75.00'), condition=Item.CONDITION_GOOD,
        )

    def test_mark_sold(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.post(reverse('marketplace:item_mark_sold', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.STATUS_SOLD)

    def test_mark_sold_forbidden_for_non_owner(self):
        other = User.objects.create_user(username='other', password='testpass123')
        self.client.login(username='other', password='testpass123')
        response = self.client.post(reverse('marketplace:item_mark_sold', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 403)

    def test_mark_sold_twice_is_handled_gracefully(self):
        self.client.login(username='seller', password='testpass123')
        self.client.post(reverse('marketplace:item_mark_sold', kwargs={'pk': self.item.pk}))

        response = self.client.post(
            reverse('marketplace:item_mark_sold', kwargs={'pk': self.item.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This listing is already marked as sold.')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class FavoriteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='testpass123')
        self.seller = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.seller, category=self.cat,
            title='Fav Item', description='An item to test favorites functionality',
            price=Decimal('30.00'), condition=Item.CONDITION_GOOD,
        )
        self.client.login(username='buyer', password='testpass123')

    def test_add_favorite(self):
        response = self.client.post(reverse('marketplace:item_favorite', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=self.user, item=self.item).exists())

    def test_remove_favorite(self):
        Favorite.objects.create(user=self.user, item=self.item)
        response = self.client.post(reverse('marketplace:item_favorite', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Favorite.objects.filter(user=self.user, item=self.item).exists())

    def test_favorites_list(self):
        Favorite.objects.create(user=self.user, item=self.item)
        response = self.client.get(reverse('marketplace:favorites'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fav Item')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MessageViewTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username='buyer', password='testpass123')
        self.seller = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.seller, category=self.cat,
            title='Message Test', description='A test item for messaging tests',
            price=Decimal('40.00'), condition=Item.CONDITION_GOOD,
        )

    def test_message_thread_loads(self):
        self.client.login(username='buyer', password='testpass123')
        response = self.client.get(reverse('marketplace:item_messages', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Message Test')

    def test_send_message(self):
        self.client.login(username='buyer', password='testpass123')
        response = self.client.post(
            reverse('marketplace:item_messages', kwargs={'pk': self.item.pk}),
            {'body': 'Is this still available?'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Message.objects.filter(item=self.item, sender=self.buyer).exists())

    def test_message_requires_login(self):
        response = self.client.get(reverse('marketplace:item_messages', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)

    def test_draft_item_message_blocked(self):
        self.item.status = Item.STATUS_DRAFT
        self.item.save()
        self.client.login(username='buyer', password='testpass123')
        response = self.client.get(reverse('marketplace:item_messages', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)

    def test_messages_inbox_requires_login(self):
        response = self.client.get(reverse('marketplace:messages_inbox'))
        self.assertEqual(response.status_code, 302)

    def test_buyer_messages_inbox_shows_thread(self):
        Message.objects.create(
            item=self.item,
            sender=self.buyer,
            recipient=self.seller,
            body='Is this still available?',
        )
        self.client.login(username='buyer', password='testpass123')

        response = self.client.get(reverse('marketplace:messages_inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Message Test')
        self.assertContains(response, 'seller')

    def test_seller_messages_inbox_shows_buyer_thread(self):
        Message.objects.create(
            item=self.item,
            sender=self.buyer,
            recipient=self.seller,
            body='I want to pick this up tomorrow.',
        )
        self.client.login(username='seller', password='testpass123')

        response = self.client.get(reverse('marketplace:messages_inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'buyer')
        self.assertContains(response, f"{reverse('marketplace:item_messages', kwargs={'pk': self.item.pk})}?recipient={self.buyer.pk}")

    def test_seller_can_reply_to_selected_buyer_thread(self):
        Message.objects.create(
            item=self.item,
            sender=self.buyer,
            recipient=self.seller,
            body='Can we meet on campus?',
        )
        self.client.login(username='seller', password='testpass123')

        response = self.client.post(
            reverse('marketplace:item_messages', kwargs={'pk': self.item.pk}),
            {'body': 'Yes, library entrance works.', 'recipient': str(self.buyer.pk)},
        )

        self.assertRedirects(
            response,
            f"{reverse('marketplace:item_messages', kwargs={'pk': self.item.pk})}?recipient={self.buyer.pk}",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Message.objects.filter(
                item=self.item,
                sender=self.seller,
                recipient=self.buyer,
                body='Yes, library entrance works.',
            ).exists()
        )

    def test_unread_message_badge_shows_in_navigation(self):
        Message.objects.create(
            item=self.item,
            sender=self.buyer,
            recipient=self.seller,
            body='Unread note for nav badge.',
        )
        self.client.login(username='seller', password='testpass123')

        response = self.client.get(reverse('marketplace:browse'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'message-nav-badge')
        self.assertContains(response, '>1<', html=False)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ReportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reporter', password='testpass123')
        self.seller = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.item = Item.objects.create(
            seller=self.seller, category=self.cat,
            title='Report Me', description='This is an item to be reported',
            price=Decimal('20.00'), condition=Item.CONDITION_GOOD,
        )

    def test_report_page_loads(self):
        self.client.login(username='reporter', password='testpass123')
        response = self.client.get(reverse('marketplace:item_report', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)

    def test_submit_report(self):
        self.client.login(username='reporter', password='testpass123')
        response = self.client.post(
            reverse('marketplace:item_report', kwargs={'pk': self.item.pk}),
            {'reason': Report.REASON_SPAM, 'comment': 'This is spam'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Report.objects.filter(item=self.item, reporter=self.user).exists())

    def test_cannot_report_own_item(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('marketplace:item_report', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 302)

    def test_duplicate_report_blocked(self):
        Report.objects.create(item=self.item, reporter=self.user, reason=Report.REASON_SPAM)
        self.client.login(username='reporter', password='testpass123')
        response = self.client.post(
            reverse('marketplace:item_report', kwargs={'pk': self.item.pk}),
            {'reason': Report.REASON_FRAUD, 'comment': 'Also fraud'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Report.objects.filter(item=self.item, reporter=self.user).count(), 1)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='testpass123')
        self.cat = Category.objects.create(name='Test', slug='test')
        self.client.login(username='seller', password='testpass123')

    def test_dashboard_loads(self):
        response = self.client.get(reverse('marketplace:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_sections(self):
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Published', description='A published item for testing',
            price=Decimal('10.00'), condition=Item.CONDITION_NEW,
            status=Item.STATUS_PUBLISHED,
        )
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='My Draft', description='A draft item for testing',
            price=Decimal('15.00'), condition=Item.CONDITION_GOOD,
            status=Item.STATUS_DRAFT,
        )
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Sold Out', description='A sold item for testing',
            price=Decimal('20.00'), condition=Item.CONDITION_FAIR,
            status=Item.STATUS_SOLD,
        )
        response = self.client.get(reverse('marketplace:dashboard'))
        self.assertEqual(len(response.context['draft_items']), 1)
        self.assertEqual(len(response.context['published_items']), 1)
        self.assertEqual(len(response.context['sold_items']), 1)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('marketplace:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_recently_viewed_order(self):
        items = []
        for i in range(3):
            item = Item.objects.create(
                seller=self.user, category=self.cat,
                title=f'View {i}', description=f'Item to view for testing order {i}',
                price=Decimal('10.00'), condition=Item.CONDITION_NEW,
            )
            items.append(item)
        # View items in order: 0, 1, 2 -> recently viewed should be [2, 1, 0]
        for item in items:
            self.client.get(reverse('marketplace:item_detail', kwargs={'pk': item.pk}))
        response = self.client.get(reverse('marketplace:dashboard'))
        rv = list(response.context['recently_viewed'])
        self.assertEqual(rv[0].pk, items[2].pk)
        self.assertEqual(rv[1].pk, items[1].pk)
        self.assertEqual(rv[2].pk, items[0].pk)

    def test_dashboard_exposes_listing_counts(self):
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Draft Count', description='Draft listing used for count checks.',
            price=Decimal('10.00'), condition=Item.CONDITION_NEW,
            status=Item.STATUS_DRAFT,
        )
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Published Count', description='Published listing used for count checks.',
            price=Decimal('11.00'), condition=Item.CONDITION_GOOD,
            status=Item.STATUS_PUBLISHED,
        )
        Item.objects.create(
            seller=self.user, category=self.cat,
            title='Sold Count', description='Sold listing used for count checks.',
            price=Decimal('12.00'), condition=Item.CONDITION_FAIR,
            status=Item.STATUS_SOLD,
        )

        response = self.client.get(reverse('marketplace:dashboard'))

        self.assertEqual(response.context['listing_counts']['all'], 3)
        self.assertEqual(response.context['listing_counts']['draft'], 1)
        self.assertEqual(response.context['listing_counts']['published'], 1)
        self.assertEqual(response.context['listing_counts']['sold'], 1)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AdminPanelTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='adminuser',
            password='testpass123',
            is_staff=True,
        )
        self.member = User.objects.create_user(
            username='memberuser',
            password='testpass123',
            email='member@example.com',
        )
        self.category = Category.objects.create(name='Admin Test', slug='admin-test')
        self.item = Item.objects.create(
            seller=self.member,
            category=self.category,
            title='Flagged Listing',
            description='This listing exists to test the admin moderation panel.',
            price=Decimal('49.99'),
            condition=Item.CONDITION_GOOD,
            status=Item.STATUS_DRAFT,
        )
        self.report = Report.objects.create(
            item=self.item,
            reporter=self.staff,
            reason=Report.REASON_SPAM,
            comment='This needs review.',
        )
        self.message = Message.objects.create(
            item=self.item,
            sender=self.member,
            recipient=self.staff,
            body='Can you review this listing for me?',
        )

    def test_admin_dashboard_requires_staff(self):
        self.client.login(username='memberuser', password='testpass123')
        response = self.client.get(reverse('marketplace:admin_dashboard'))
        self.assertRedirects(response, reverse('marketplace:browse'))

    def test_admin_dashboard_loads_for_staff(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.get(reverse('marketplace:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Dashboard')

    def test_admin_item_action_can_publish_draft(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.post(
            reverse('marketplace:admin_item_action', kwargs={'pk': self.item.pk}),
            {'action': 'publish'},
        )
        self.assertRedirects(response, reverse('marketplace:admin_items'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.STATUS_PUBLISHED)

    def test_admin_report_action_unpublishes_item_and_resolves_report(self):
        self.client.login(username='adminuser', password='testpass123')
        self.item.status = Item.STATUS_PUBLISHED
        self.item.save(update_fields=['status'])

        response = self.client.post(
            reverse('marketplace:admin_report_action', kwargs={'pk': self.report.pk}),
            {'action': 'unpublish_item'},
        )

        self.assertRedirects(response, reverse('marketplace:admin_reports'))
        self.item.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.item.status, Item.STATUS_DRAFT)
        self.assertEqual(self.report.status, Report.STATUS_RESOLVED)
        self.assertEqual(self.report.reviewed_by, self.staff)
        self.assertIsNotNone(self.report.reviewed_at)

    def test_admin_user_action_can_deactivate_member(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.post(
            reverse('marketplace:admin_user_action', kwargs={'pk': self.member.pk}),
            {'action': 'deactivate'},
        )
        self.assertRedirects(response, reverse('marketplace:admin_users'))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_admin_category_create_works(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.post(
            reverse('marketplace:admin_category_create'),
            {'name': 'Furniture', 'slug': ''},
        )
        self.assertRedirects(response, reverse('marketplace:admin_categories'))
        self.assertTrue(Category.objects.filter(name='Furniture', slug='furniture').exists())

    def test_admin_message_action_marks_message_read(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.post(
            reverse('marketplace:admin_message_action', kwargs={'pk': self.message.pk}),
            {'action': 'mark_read'},
        )
        self.assertRedirects(response, reverse('marketplace:admin_messages'))
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_read)
