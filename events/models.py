from django.core.exceptions import ValidationError
from django.db import models


class Vendor(models.Model):
    """Vendor representing an event organizer or venue partner."""

    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'vendor'
        verbose_name_plural = 'vendors'
        ordering = ['name']

    def __str__(self):
        return self.name


class Event(models.Model):
    """Event model representing bookable events organized by vendors."""

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='events'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    total_seats = models.PositiveIntegerField()
    available_seats = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'event'
        verbose_name_plural = 'events'
        ordering = ['-start_datetime']
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_seats__gt=0),
                name='event_total_seats_gt_0'
            ),
            models.CheckConstraint(
                check=models.Q(available_seats__gte=0),
                name='event_available_seats_gte_0'
            ),
            models.CheckConstraint(
                check=models.Q(available_seats__lte=models.F('total_seats')),
                name='event_available_seats_lte_total_seats'
            ),
            models.CheckConstraint(
                check=models.Q(end_datetime__gte=models.F('start_datetime')),
                name='event_end_datetime_gte_start_datetime'
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.vendor.name})"

    def clean(self):
        super().clean()
        errors = {}

        if self.total_seats is not None and self.total_seats <= 0:
            errors['total_seats'] = 'Total seats must be a positive integer greater than zero.'

        # If available_seats not set, it defaults to total_seats
        if self.available_seats is None and self.total_seats is not None:
            self.available_seats = self.total_seats

        if self.available_seats is not None:
            if self.available_seats < 0:
                errors['available_seats'] = 'Available seats cannot be negative.'
            elif self.total_seats is not None and self.available_seats > self.total_seats:
                errors['available_seats'] = 'Available seats cannot exceed total seats.'

        if self.start_datetime and self.end_datetime:
            if self.end_datetime < self.start_datetime:
                errors['end_datetime'] = 'End datetime cannot be earlier than start datetime.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.available_seats is None and self.total_seats is not None:
            self.available_seats = self.total_seats
        self.full_clean()
        super().save(*args, **kwargs)


class Booking(models.Model):
    """Booking made by an authenticated customer for an event."""

    class BookingStatus(models.TextChoices):
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.CONFIRMED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'booking'
        verbose_name_plural = 'bookings'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='booking_quantity_gt_0'
            ),
        ]

    def __str__(self):
        return f"Booking #{self.id} - {self.user.email} - {self.event.title} ({self.quantity} seats) [{self.status}]"

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': 'Booking quantity must be greater than zero.'})

