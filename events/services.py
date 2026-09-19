import time
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, transaction
from django.db.models import F
from django.db.models.functions import Least
from django.utils import timezone
from .models import Booking, Event


def create_booking(user, event, quantity, max_retries=5):
    """
    Create a new booking and deduct available seats atomically.
    Uses a database-level conditional update to prevent race conditions during concurrent booking attempts.
    Handles transient SQLite OperationalError (database locked) with small, bounded retries.
    """
    if quantity <= 0:
        raise ValidationError('Booking quantity must be a positive integer greater than zero.')

    if not event.is_active:
        raise ValidationError('Cannot book tickets for an inactive event.')

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                # Concurrency protection: Conditional atomic UPDATE at the DB level.
                # Only succeeds if the event is active and has sufficient available seats.
                rows_updated = Event.objects.filter(
                    id=event.id,
                    is_active=True,
                    available_seats__gte=quantity
                ).update(
                    available_seats=F('available_seats') - quantity,
                    updated_at=timezone.now()
                )

                if rows_updated != 1:
                    event.refresh_from_db()
                    if not event.is_active:
                        raise ValidationError('Cannot book tickets for an inactive event.')
                    raise ValidationError(
                        f'Insufficient seats available. Requested: {quantity}, Available: {event.available_seats}.'
                    )

                # Create confirmed booking within the same atomic transaction
                booking = Booking.objects.create(
                    user=user,
                    event=event,
                    quantity=quantity,
                    status=Booking.BookingStatus.CONFIRMED
                )

            return booking

        except OperationalError as exc:
            # Handle SQLite transient database locking
            if 'locked' in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise


def cancel_booking(booking, user, max_retries=5):
    """
    Cancel an existing booking and restore seats to the event atomically.
    Protects against concurrent cancellations using atomic status transition.
    Handles transient SQLite OperationalError (database locked) with small, bounded retries.
    """
    if booking.user != user:
        raise PermissionDenied('You do not have permission to cancel this booking.')

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                # Concurrency protection: Atomically transition status from CONFIRMED to CANCELLED.
                # If another request already cancelled it, rows_updated will be 0.
                rows_updated = Booking.objects.filter(
                    id=booking.id,
                    status=Booking.BookingStatus.CONFIRMED
                ).update(
                    status=Booking.BookingStatus.CANCELLED,
                    updated_at=timezone.now()
                )

                if rows_updated != 1:
                    booking.refresh_from_db()
                    if booking.status == Booking.BookingStatus.CANCELLED:
                        raise ValidationError('This booking is already cancelled.')
                    raise ValidationError('This booking cannot be cancelled.')

                # Atomically restore seats to the event without exceeding total_seats
                Event.objects.filter(id=booking.event_id).update(
                    available_seats=Least(
                        F('total_seats'),
                        F('available_seats') + booking.quantity
                    ),
                    updated_at=timezone.now()
                )

                booking.refresh_from_db()

            return booking

        except OperationalError as exc:
            # Handle SQLite transient database locking
            if 'locked' in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
