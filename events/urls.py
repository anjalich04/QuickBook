from django.urls import path
from .views import (
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
    EventDetailView,
    EventListView,
)

urlpatterns = [
    # Event endpoints
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),

    # Booking endpoints
    path('bookings/', BookingListCreateView.as_view(), name='booking-list-create'),
    path('bookings/<int:pk>/', BookingDetailView.as_view(), name='booking-detail'),
    path('bookings/<int:pk>/cancel/', BookingCancelView.as_view(), name='booking-cancel'),
]
