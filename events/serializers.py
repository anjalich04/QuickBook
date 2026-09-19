from rest_framework import serializers
from .models import Booking, Event, Vendor


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for vendor details."""

    class Meta:
        model = Vendor
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'address',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EventSerializer(serializers.ModelSerializer):
    """Serializer for public event listing and detail."""
    vendor_details = VendorSerializer(source='vendor', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'vendor',
            'vendor_details',
            'title',
            'description',
            'location',
            'start_datetime',
            'end_datetime',
            'total_seats',
            'available_seats',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'available_seats', 'created_at', 'updated_at']


class BookingSerializer(serializers.ModelSerializer):
    """Serializer for viewing customer bookings."""
    event_details = EventSerializer(source='event', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'user',
            'event',
            'event_details',
            'quantity',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'event',
            'event_details',
            'quantity',
            'status',
            'created_at',
            'updated_at',
        ]


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for validating booking creation requests."""
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.all(),
        required=True
    )
    quantity = serializers.IntegerField(
        min_value=1,
        required=True
    )

    def validate_event(self, value):
        if not value.is_active:
            raise serializers.ValidationError('Cannot book tickets for an inactive event.')
        return value

    def validate(self, attrs):
        event = attrs.get('event')
        quantity = attrs.get('quantity')

        if event and quantity:
            if quantity > event.available_seats:
                raise serializers.ValidationError(
                    {'quantity': f'Requested quantity ({quantity}) exceeds available seats ({event.available_seats}).'}
                )

        return attrs
