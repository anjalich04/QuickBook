
import threading
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Booking, Event, Vendor
from .services import cancel_booking, create_booking

User = get_user_model()


class VendorModelTests(TestCase):
    """Unit tests for the Vendor model."""

    def test_vendor_created_successfully(self):
        vendor = Vendor.objects.create(
            name='Grand Plaza Events',
            email='contact@grandplaza.com',
            phone='+1234567890',
            address='123 Main Street, Suite 400'
        )
        self.assertEqual(vendor.name, 'Grand Plaza Events')
        self.assertEqual(str(vendor), 'Grand Plaza Events')
        self.assertIsNotNone(vendor.created_at)
        self.assertIsNotNone(vendor.updated_at)

    def test_vendor_name_required(self):
        vendor = Vendor(name='', email='invalid@vendor.com')
        with self.assertRaises(ValidationError):
            vendor.full_clean()


class EventModelTests(TestCase):
    """Unit tests for the Event model and its constraints."""

    def setUp(self):
        self.vendor = Vendor.objects.create(
            name='Tech Conferences LLC',
            email='info@techconf.org'
        )
        self.now = timezone.now()

    def test_event_created_successfully_and_available_seats_defaults(self):
        event = Event.objects.create(
            vendor=self.vendor,
            title='Tech Summit 2026',
            description='Annual tech innovation summit.',
            location='Convention Hall A',
            start_datetime=self.now + timedelta(days=10),
            end_datetime=self.now + timedelta(days=10, hours=8),
            total_seats=100
        )
        self.assertEqual(event.total_seats, 100)
        self.assertEqual(event.available_seats, 100)
        self.assertEqual(event.vendor, self.vendor)
        self.assertTrue(event.is_active)
        self.assertIn('Tech Summit 2026', str(event))

    def test_event_total_seats_cannot_be_zero_or_negative(self):
        event = Event(
            vendor=self.vendor,
            title='Invalid Seats Event',
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=2),
            total_seats=0
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_event_available_seats_cannot_be_negative(self):
        event = Event(
            vendor=self.vendor,
            title='Negative Available Seats',
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=2),
            total_seats=50,
            available_seats=-5
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_event_available_seats_cannot_exceed_total_seats(self):
        event = Event(
            vendor=self.vendor,
            title='Overbooked Event',
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=2),
            total_seats=50,
            available_seats=60
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_event_end_datetime_before_start_datetime_invalid(self):
        event = Event(
            vendor=self.vendor,
            title='Invalid Dates Event',
            start_datetime=self.now + timedelta(days=5),
            end_datetime=self.now + timedelta(days=4),
            total_seats=50
        )
        with self.assertRaises(ValidationError):
            event.full_clean()


class BookingModelTests(TestCase):
    """Unit tests for the Booking model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='bookinguser@example.com',
            password='password123',
            first_name='Booking',
            last_name='User'
        )
        self.vendor = Vendor.objects.create(name='City Arena')
        self.now = timezone.now()
        self.event = Event.objects.create(
            vendor=self.vendor,
            title='Concert Night',
            start_datetime=self.now + timedelta(days=2),
            end_datetime=self.now + timedelta(days=2, hours=3),
            total_seats=100
        )

    def test_booking_created_successfully(self):
        booking = Booking.objects.create(
            user=self.user,
            event=self.event,
            quantity=2,
            status=Booking.BookingStatus.CONFIRMED
        )
        self.assertEqual(booking.quantity, 2)
        self.assertEqual(booking.status, Booking.BookingStatus.CONFIRMED)
        self.assertIn('Concert Night', str(booking))

    def test_booking_quantity_cannot_be_zero_or_negative(self):
        booking = Booking(
            user=self.user,
            event=self.event,
            quantity=0,
            status=Booking.BookingStatus.CONFIRMED
        )
        with self.assertRaises(ValidationError):
            booking.full_clean()


class EventAPITests(APITestCase):
    """Integration tests for Event browsing, filtering, search, and pagination APIs."""

    def setUp(self):
        self.vendor_a = Vendor.objects.create(name='Mega Events Inc')
        self.vendor_b = Vendor.objects.create(name='Acoustic Sessions')
        self.now = timezone.now()

        self.event1 = Event.objects.create(
            vendor=self.vendor_a,
            title='Python Conference 2026',
            description='Annual Python Developer conference.',
            location='San Francisco, CA',
            start_datetime=self.now + timedelta(days=10),
            end_datetime=self.now + timedelta(days=12),
            total_seats=200,
            available_seats=200,
            is_active=True
        )
        self.event2 = Event.objects.create(
            vendor=self.vendor_b,
            title='Jazz Under the Stars',
            description='Live outdoor jazz performance.',
            location='Austin, TX',
            start_datetime=self.now + timedelta(days=5),
            end_datetime=self.now + timedelta(days=5, hours=4),
            total_seats=50,
            available_seats=50,
            is_active=True
        )
        self.inactive_event = Event.objects.create(
            vendor=self.vendor_a,
            title='Private Gala',
            description='Private invite-only gala.',
            location='New York, NY',
            start_datetime=self.now + timedelta(days=20),
            end_datetime=self.now + timedelta(days=20, hours=5),
            total_seats=30,
            available_seats=30,
            is_active=False
        )
        self.events_url = reverse('event-list')

    def test_list_active_events_public(self):
        response = self.client.get(self.events_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in response.data['results']]
        self.assertIn('Python Conference 2026', titles)
        self.assertIn('Jazz Under the Stars', titles)
        self.assertNotIn('Private Gala', titles)

    def test_event_detail_public(self):
        detail_url = reverse('event-detail', kwargs={'pk': self.event1.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Python Conference 2026')
        self.assertEqual(response.data['vendor_details']['name'], 'Mega Events Inc')

    def test_inactive_event_detail_returns_404(self):
        detail_url = reverse('event-detail', kwargs={'pk': self.inactive_event.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_event_search_filter(self):
        response = self.client.get(self.events_url, {'search': 'jazz'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Jazz Under the Stars')

    def test_event_location_filter(self):
        response = self.client.get(self.events_url, {'location': 'Austin'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['location'], 'Austin, TX')

    def test_event_vendor_filter(self):
        response = self.client.get(self.events_url, {'vendor': self.vendor_b.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['vendor'], self.vendor_b.id)

    def test_event_pagination(self):
        response = self.client.get(self.events_url, {'page_size': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['count'], 2)

    def test_event_ordering(self):
        response = self.client.get(self.events_url, {'ordering': '-title'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['title'], 'Python Conference 2026')
        self.assertEqual(response.data['results'][1]['title'], 'Jazz Under the Stars')


class BookingAPITests(APITestCase):
    """Integration tests for booking creation, history, cancellation, and validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='password123',
            first_name='Jane',
            last_name='Customer'
        )
        self.token = Token.objects.create(user=self.user)

        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='password123',
            first_name='Bob',
            last_name='Other'
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.vendor = Vendor.objects.create(name='Global Shows')
        self.now = timezone.now()

        self.event = Event.objects.create(
            vendor=self.vendor,
            title='Arena Concert',
            location='Main Stadium',
            start_datetime=self.now + timedelta(days=7),
            end_datetime=self.now + timedelta(days=7, hours=3),
            total_seats=20,
            available_seats=20,
            is_active=True
        )

        self.inactive_event = Event.objects.create(
            vendor=self.vendor,
            title='Cancelled Tour',
            location='Hall B',
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=2),
            total_seats=10,
            available_seats=10,
            is_active=False
        )

        self.bookings_url = reverse('booking-list-create')

    def test_unauthenticated_booking_access_rejected(self):
        response = self.client.get(self.bookings_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_booking_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        payload = {'event': self.event.id, 'quantity': 3}
        response = self.client.post(self.bookings_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['quantity'], 3)
        self.assertEqual(response.data['status'], 'CONFIRMED')

        self.event.refresh_from_db()
        self.assertEqual(self.event.available_seats, 17)

    def test_create_booking_exceeding_seats_fails(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        payload = {'event': self.event.id, 'quantity': 25}
        response = self.client.post(self.bookings_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.event.refresh_from_db()
        self.assertEqual(self.event.available_seats, 20)

    def test_create_booking_inactive_event_fails(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        payload = {'event': self.inactive_event.id, 'quantity': 2}
        response = self.client.post(self.bookings_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_history_isolated_to_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.client.post(self.bookings_url, {'event': self.event.id, 'quantity': 2}, format='json')

        # Other user's booking
        Booking.objects.create(user=self.other_user, event=self.event, quantity=1, status='CONFIRMED')

        response = self.client.get(self.bookings_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['user'], self.user.id)

    def test_booking_detail_owner_success(self):
        booking = Booking.objects.create(user=self.user, event=self.event, quantity=2, status='CONFIRMED')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        detail_url = reverse('booking-detail', kwargs={'pk': booking.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], booking.id)
        self.assertEqual(response.data['quantity'], 2)

    def test_booking_detail_other_user_forbidden_or_404(self):
        booking = Booking.objects.create(user=self.user, event=self.event, quantity=2, status='CONFIRMED')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        detail_url = reverse('booking-detail', kwargs={'pk': booking.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_booking_success_and_restores_seats(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        booking_resp = self.client.post(self.bookings_url, {'event': self.event.id, 'quantity': 4}, format='json')
        booking_id = booking_resp.data['id']

        self.event.refresh_from_db()
        self.assertEqual(self.event.available_seats, 16)

        cancel_url = reverse('booking-cancel', kwargs={'pk': booking_id})
        cancel_resp = self.client.post(cancel_url)

        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_resp.data['booking']['status'], 'CANCELLED')

        self.event.refresh_from_db()
        self.assertEqual(self.event.available_seats, 20)

    def test_cancel_already_cancelled_booking_fails(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        booking_resp = self.client.post(self.bookings_url, {'event': self.event.id, 'quantity': 2}, format='json')
        booking_id = booking_resp.data['id']

        cancel_url = reverse('booking-cancel', kwargs={'pk': booking_id})
        self.client.post(cancel_url)
        second_cancel = self.client.post(cancel_url)

        self.assertEqual(second_cancel.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_other_user_booking_fails(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        booking_resp = self.client.post(self.bookings_url, {'event': self.event.id, 'quantity': 2}, format='json')
        booking_id = booking_resp.data['id']

        # Switch to other user
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        cancel_url = reverse('booking-cancel', kwargs={'pk': booking_id})
        response = self.client.post(cancel_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_booking_unauthenticated_rejected(self):
        booking = Booking.objects.create(user=self.user, event=self.event, quantity=2, status='CONFIRMED')
        cancel_url = reverse('booking-cancel', kwargs={'pk': booking.id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BookingConcurrencyTests(TransactionTestCase):
    """Stress tests verifying atomic concurrency handling for bookings and cancellations."""

    def setUp(self):
        self.vendor = Vendor.objects.create(name='Festival Grounds LLC')
        self.now = timezone.now()

        self.user_a = User.objects.create_user(email='concurrent_a@test.com', password='p', first_name='A', last_name='U')
        self.user_b = User.objects.create_user(email='concurrent_b@test.com', password='p', first_name='B', last_name='U')

    def test_concurrent_bookings_do_not_oversell_capacity(self):
        """
        Scenario: Event has 10 seats remaining.
        Two concurrent threads each request 8 seats.
        Invariant: Exactly 1 succeeds, 1 fails. Available seats must equal 2 (10 - 8), never negative.
        """
        event = Event.objects.create(
            vendor=self.vendor,
            title='High Demand Event',
            start_datetime=self.now + timedelta(days=5),
            end_datetime=self.now + timedelta(days=5, hours=2),
            total_seats=10,
            available_seats=10,
            is_active=True
        )

        results = []
        barrier = threading.Barrier(2)

        def make_booking(user):
            connections.close_all()
            try:
                barrier.wait()
                b = create_booking(user=user, event=event, quantity=8)
                results.append(('success', b))
            except Exception as exc:
                results.append(('error', exc))
            finally:
                connections.close_all()

        t1 = threading.Thread(target=make_booking, args=(self.user_a,))
        t2 = threading.Thread(target=make_booking, args=(self.user_b,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] == 'success']
        errors = [r for r in results if r[0] == 'error']

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)

        event.refresh_from_db()
        confirmed_bookings = Booking.objects.filter(event=event, status=Booking.BookingStatus.CONFIRMED)
        total_confirmed_quantity = sum(b.quantity for b in confirmed_bookings)

        self.assertEqual(total_confirmed_quantity, 8)
        self.assertEqual(event.available_seats, 2)
        self.assertGreaterEqual(event.available_seats, 0)
        self.assertEqual(event.available_seats, event.total_seats - total_confirmed_quantity)

    def test_concurrent_cancellations_prevent_double_restoration(self):
        """
        Scenario: User has a confirmed booking for 3 seats (event 5 seats -> 2 remaining).
        Two simultaneous requests attempt to cancel the exact same booking.
        Invariant: Seats restored only once (available becomes 5, never 8). Status is CANCELLED.
        """
        event = Event.objects.create(
            vendor=self.vendor,
            title='Single Cancel Event',
            start_datetime=self.now + timedelta(days=5),
            end_datetime=self.now + timedelta(days=5, hours=2),
            total_seats=5,
            available_seats=5,
            is_active=True
        )
        booking = create_booking(user=self.user_a, event=event, quantity=3)
        event.refresh_from_db()
        self.assertEqual(event.available_seats, 2)

        results = []
        barrier = threading.Barrier(2)

        def make_cancel():
            connections.close_all()
            try:
                barrier.wait()
                res = cancel_booking(booking=booking, user=self.user_a)
                results.append(('success', res))
            except Exception as exc:
                results.append(('error', exc))
            finally:
                connections.close_all()

        t1 = threading.Thread(target=make_cancel)
        t2 = threading.Thread(target=make_cancel)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] == 'success']
        errors = [r for r in results if r[0] == 'error']

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)

        event.refresh_from_db()
        self.assertEqual(event.available_seats, 5)
        self.assertLessEqual(event.available_seats, event.total_seats)


class SwaggerDocumentationTests(APITestCase):
    """Tests for the OpenAPI schema and Swagger UI documentation endpoints."""

    def test_openapi_schema_endpoint_accessible(self):
        """Confirm /api/schema/ returns 200 OK with OpenAPI schema content."""
        response = self.client.get('/api/schema/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('QuickBook API', str(response.content))

    def test_swagger_ui_endpoint_accessible(self):
        """Confirm /api/docs/ returns 200 OK and serves Swagger UI."""
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'swagger-ui')

