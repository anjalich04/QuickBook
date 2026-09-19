from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services import find_available_binary_placement
from events.models import Booking, Event, Vendor

User = get_user_model()


class CustomStaffDashboardTests(TestCase):
    """Integration tests for the custom staff dashboard."""

    def setUp(self):
        # Create a staff user
        self.staff_user = User.objects.create_superuser(
            email='admin@quickbook.com',
            password='StaffPassword123!',
            first_name='Admin',
            last_name='Staff'
        )

        # Create a regular customer
        self.customer = User.objects.create_user(
            email='customer1@example.com',
            password='CustomerPassword123!',
            first_name='John',
            last_name='Customer'
        )

        # Create vendor and event
        self.vendor = Vendor.objects.create(
            name='Global Arena LLC',
            email='contact@globalarena.com',
            phone='+1234567890',
            address='100 Main St'
        )
        self.now = timezone.now()
        self.event = Event.objects.create(
            vendor=self.vendor,
            title='Rock Concert 2026',
            description='Live energetic rock concert.',
            location='Main Stadium',
            start_datetime=self.now + timedelta(days=5),
            end_datetime=self.now + timedelta(days=5, hours=3),
            total_seats=100,
            available_seats=95,
            is_active=True
        )

        # Create booking
        self.booking = Booking.objects.create(
            user=self.customer,
            event=self.event,
            quantity=5,
            status=Booking.BookingStatus.CONFIRMED
        )

    # 1. Staff Authentication & Access Control
    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard-login'), response.url)

    def test_non_staff_user_denied_dashboard_access(self):
        self.client.login(email='customer1@example.com', password='CustomerPassword123!')
        response = self.client.get(reverse('dashboard-home'), follow=True)
        # Should be redirected back to login with access denied message
        self.assertContains(response, 'Access denied')

    def test_staff_user_can_access_dashboard_home(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')

    def test_staff_login_view_success(self):
        login_url = reverse('dashboard-login')
        response = self.client.post(login_url, {
            'email': 'admin@quickbook.com',
            'password': 'StaffPassword123!'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].is_staff)

    def test_non_staff_login_attempt_rejected(self):
        login_url = reverse('dashboard-login')
        response = self.client.post(login_url, {
            'email': 'customer1@example.com',
            'password': 'CustomerPassword123!'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'does not have staff permissions')

    def test_staff_logout_view(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    # 2. Dashboard Analytics & Statistics
    def test_dashboard_home_statistics(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 200)

        # 1 customer (non-staff), 1 vendor, 1 event, 1 booking
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_vendors'], 1)
        self.assertEqual(response.context['total_events'], 1)
        self.assertEqual(response.context['total_bookings'], 1)

    # 3. Customer Management
    def test_customer_list_view(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-customers'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'customer1@example.com')
        self.assertContains(response, 'John Customer')

    def test_customer_search(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        # Search match
        response = self.client.get(reverse('dashboard-customers'), {'search': 'John'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'customer1@example.com')

        # Search no match
        response_nomatch = self.client.get(reverse('dashboard-customers'), {'search': 'NonExistentPerson'})
        self.assertEqual(response_nomatch.status_code, 200)
        self.assertContains(response_nomatch, 'No customers matching criteria found')

    def test_customer_pagination(self):
        # Create 15 extra customers
        for i in range(15):
            User.objects.create_user(
                email=f'extra_customer_{i}@example.com',
                password='password123',
                first_name='Extra',
                last_name=f'User {i}'
            )

        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-customers'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['customers']), 10)

        # Page 2
        response_p2 = self.client.get(reverse('dashboard-customers'), {'page': 2})
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context['customers']), 6)

    def test_customer_detail_and_tree(self):
        # Create referral tree: customer -> child_left
        parent, pos = find_available_binary_placement(self.customer)
        child = User.objects.create_user(
            email='child@example.com',
            password='password123',
            first_name='Child',
            last_name='User',
            referred_by=parent,
            referral_position=pos,
            sponsor=self.customer
        )

        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-customer-detail', kwargs={'user_id': self.customer.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'customer1@example.com')
        self.assertContains(response, 'child@example.com')
        self.assertEqual(response.context['stats']['left_team_count'], 1)
        self.assertEqual(response.context['stats']['total_team_count'], 1)

    # 4. Vendor Management
    def test_vendor_list(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-vendors'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Global Arena LLC')

    def test_vendor_create_success(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        data = {
            'name': 'New Tech Venue',
            'email': 'tech@venue.com',
            'phone': '+1999888777',
            'address': '500 Tech Blvd'
        }
        response = self.client.post(reverse('dashboard-vendor-add'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Vendor.objects.filter(name='New Tech Venue').exists())

    def test_vendor_update_success(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        data = {
            'name': 'Global Arena Updated',
            'email': 'updated@globalarena.com',
            'phone': '+1234567890',
            'address': '100 Main St Suite 200'
        }
        response = self.client.post(reverse('dashboard-vendor-edit', kwargs={'vendor_id': self.vendor.id}), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.name, 'Global Arena Updated')

    def test_vendor_detail(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-vendor-detail', kwargs={'vendor_id': self.vendor.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Global Arena LLC')
        self.assertContains(response, 'Rock Concert 2026')

    # 5. Event Management
    def test_event_list_and_filters(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-events'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rock Concert 2026')

        # Filter by vendor
        response_vendor = self.client.get(reverse('dashboard-events'), {'vendor': self.vendor.id})
        self.assertEqual(response_vendor.status_code, 200)
        self.assertEqual(len(response_vendor.context['events']), 1)

        # Filter by active status
        response_active = self.client.get(reverse('dashboard-events'), {'status': 'active'})
        self.assertEqual(response_active.status_code, 200)
        self.assertEqual(len(response_active.context['events']), 1)

    def test_event_create_success(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        data = {
            'vendor': self.vendor.id,
            'title': 'Jazz Gala Night',
            'description': 'Smooth evening jazz.',
            'location': 'Harbor Hall',
            'start_datetime': (self.now + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (self.now + timedelta(days=10, hours=4)).strftime('%Y-%m-%dT%H:%M'),
            'total_seats': 150,
            'available_seats': 150,
            'is_active': True,
        }
        response = self.client.post(reverse('dashboard-event-add'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Event.objects.filter(title='Jazz Gala Night').exists())

    def test_event_update_success(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        data = {
            'vendor': self.vendor.id,
            'title': 'Rock Concert 2026 (Extended)',
            'description': self.event.description,
            'location': self.event.location,
            'start_datetime': self.event.start_datetime.strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': self.event.end_datetime.strftime('%Y-%m-%dT%H:%M'),
            'total_seats': 120,
            'available_seats': 115,
            'is_active': True,
        }
        response = self.client.post(reverse('dashboard-event-edit', kwargs={'event_id': self.event.id}), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Rock Concert 2026 (Extended)')
        self.assertEqual(self.event.total_seats, 120)

    # 6. Booking Management
    def test_booking_list_and_filter(self):
        self.client.login(email='admin@quickbook.com', password='StaffPassword123!')
        response = self.client.get(reverse('dashboard-bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'customer1@example.com')
        self.assertContains(response, 'Rock Concert 2026')

        # Filter by status
        response_confirmed = self.client.get(reverse('dashboard-bookings'), {'status': 'CONFIRMED'})
        self.assertEqual(response_confirmed.status_code, 200)
        self.assertEqual(len(response_confirmed.context['bookings']), 1)

        response_cancelled = self.client.get(reverse('dashboard-bookings'), {'status': 'CANCELLED'})
        self.assertEqual(response_cancelled.status_code, 200)
        self.assertEqual(len(response_cancelled.context['bookings']), 0)

    # 7. Root Landing Page
    def test_root_landing_page_public_access(self):
        """Confirm root URL '/' returns 200 OK without authentication and displays QuickBook brand."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'QuickBook')
        self.assertContains(response, 'Event Booking Platform')
        self.assertContains(response, 'Staff Login')
