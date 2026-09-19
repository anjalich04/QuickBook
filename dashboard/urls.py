from django.urls import path
from .views import (
    BookingListView,
    CustomerDetailView,
    CustomerListView,
    DashboardHomeView,
    EventCreateView,
    EventListView,
    EventUpdateView,
    StaffLoginView,
    StaffLogoutView,
    VendorCreateView,
    VendorDetailView,
    VendorListView,
    VendorUpdateView,
)

urlpatterns = [
    path('', DashboardHomeView.as_view(), name='dashboard-home'),
    path('login/', StaffLoginView.as_view(), name='dashboard-login'),
    path('logout/', StaffLogoutView.as_view(), name='dashboard-logout'),
    path('customers/', CustomerListView.as_view(), name='dashboard-customers'),
    path('customers/<int:user_id>/', CustomerDetailView.as_view(), name='dashboard-customer-detail'),
    path('vendors/', VendorListView.as_view(), name='dashboard-vendors'),
    path('vendors/add/', VendorCreateView.as_view(), name='dashboard-vendor-add'),
    path('vendors/<int:vendor_id>/', VendorDetailView.as_view(), name='dashboard-vendor-detail'),
    path('vendors/<int:vendor_id>/edit/', VendorUpdateView.as_view(), name='dashboard-vendor-edit'),
    path('events/', EventListView.as_view(), name='dashboard-events'),
    path('events/add/', EventCreateView.as_view(), name='dashboard-event-add'),
    path('events/<int:event_id>/edit/', EventUpdateView.as_view(), name='dashboard-event-edit'),
    path('bookings/', BookingListView.as_view(), name='dashboard-bookings'),
]
