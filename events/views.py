from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import filters, generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Event
from .pagination import StandardResultsSetPagination
from .serializers import BookingCreateSerializer, BookingSerializer, EventSerializer
from .services import cancel_booking, create_booking


class EventListView(generics.ListAPIView):
    """
    Public endpoint to list active events with search, ordering, filtering, and pagination.
    """
    permission_classes = [AllowAny]
    serializer_class = EventSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['start_datetime', 'created_at', 'title', 'total_seats', 'available_seats']
    ordering = ['start_datetime']

    def get_queryset(self):
        # Public listing strictly returns active events
        queryset = Event.objects.filter(is_active=True).select_related('vendor')

        # Optional filtering by location
        location = self.request.query_params.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location.strip())

        # Optional filtering by vendor ID
        vendor_id = self.request.query_params.get('vendor')
        if vendor_id and vendor_id.isdigit():
            queryset = queryset.filter(vendor_id=int(vendor_id))

        return queryset


class EventDetailView(generics.RetrieveAPIView):
    """
    Public endpoint to retrieve details of a specific active event.
    Returns 404 if the event does not exist or is inactive.
    """
    permission_classes = [AllowAny]
    serializer_class = EventSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        # Public detail strictly allows access to active events only
        return Event.objects.filter(is_active=True).select_related('vendor')


class BookingListCreateView(generics.ListCreateAPIView):
    """
    Endpoint for customers to view their booking history or create a new booking.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BookingCreateSerializer
        return BookingSerializer

    def get_queryset(self):
        # Only return bookings belonging to the authenticated user
        return Booking.objects.filter(user=self.request.user).select_related('event', 'event__vendor').order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.validated_data['event']
        quantity = serializer.validated_data['quantity']

        try:
            booking = create_booking(user=request.user, event=event, quantity=quantity)
        except DjangoValidationError as exc:
            return Response({'error': exc.messages if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = BookingSerializer(booking)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class BookingDetailView(generics.RetrieveAPIView):
    """
    Endpoint for a customer to retrieve details of their individual booking.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        # Restrict retrieval strictly to the authenticated user's bookings
        return Booking.objects.filter(user=self.request.user).select_related('event', 'event__vendor')


@extend_schema(
    summary='Cancel a booking',
    description='Endpoint for a customer to cancel an existing confirmed booking and restore seats.',
    request=None,
    responses={
        200: inline_serializer(
            name='BookingCancelResponse',
            fields={
                'message': serializers.CharField(),
                'booking': BookingSerializer(),
            }
        ),
        400: OpenApiResponse(description='Cancellation error'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Booking not found'),
    }
)
class BookingCancelView(APIView):
    """
    Endpoint for a customer to cancel an existing confirmed booking.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking.objects.select_related('event'), pk=pk, user=request.user)

        try:
            updated_booking = cancel_booking(booking=booking, user=request.user)
        except DjangoValidationError as exc:
            return Response({'error': exc.messages if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoPermissionDenied as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                'message': 'Booking cancelled successfully.',
                'booking': BookingSerializer(updated_booking).data,
            },
            status=status.HTTP_200_OK
        )
