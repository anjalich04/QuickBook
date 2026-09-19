from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from accounts.models import User
from accounts.services import build_referral_tree, get_referral_stats
from events.models import Booking, Event, Vendor
from .forms import EventForm, StaffLoginForm, VendorForm


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only authenticated staff users can access dashboard views."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect(f"{reverse('dashboard-login')}?next={self.request.path}")
        messages.error(self.request, 'Access denied. Staff privileges are required to view this area.')
        return redirect('dashboard-login')


class StaffLoginView(View):
    """Custom dashboard staff login view."""

    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('dashboard-home')
        form = StaffLoginForm()
        return render(request, 'dashboard/login.html', {'form': form})

    def post(self, request):
        form = StaffLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            user = authenticate(request, email=email, password=password)
            if user is not None:
                if user.is_staff:
                    login(request, user)
                    next_url = request.GET.get('next') or request.POST.get('next') or reverse('dashboard-home')
                    messages.success(request, f'Welcome back, {user.first_name or user.email}!')
                    return redirect(next_url)
                else:
                    messages.error(request, 'Access denied. Your account does not have staff permissions.')
            else:
                messages.error(request, 'Invalid email or password.')

        return render(request, 'dashboard/login.html', {'form': form})


class StaffLogoutView(View):
    """Staff logout handler."""

    def get(self, request):
        logout(request)
        messages.info(request, 'You have been logged out of the staff dashboard.')
        return redirect('dashboard-login')

    def post(self, request):
        logout(request)
        messages.info(request, 'You have been logged out of the staff dashboard.')
        return redirect('dashboard-login')


class DashboardHomeView(StaffRequiredMixin, View):
    """Dashboard homepage displaying high-level system analytics."""

    def get(self, request):
        total_customers = User.objects.filter(is_staff=False).count()
        total_vendors = Vendor.objects.count()
        total_events = Event.objects.count()
        total_bookings = Booking.objects.count()

        recent_events = Event.objects.select_related('vendor').order_by('-created_at')[:5]
        recent_bookings = Booking.objects.select_related('user', 'event').order_by('-created_at')[:5]

        context = {
            'total_customers': total_customers,
            'total_vendors': total_vendors,
            'total_events': total_events,
            'total_bookings': total_bookings,
            'recent_events': recent_events,
            'recent_bookings': recent_bookings,
        }
        return render(request, 'dashboard/index.html', context)


class CustomerListView(StaffRequiredMixin, View):
    """View to list and search customer accounts."""

    def get(self, request):
        queryset = User.objects.filter(is_staff=False).select_related('referred_by', 'sponsor').order_by('-date_joined')
        search_query = request.GET.get('search', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(referral_code__icontains=search_query)
            )

        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page')
        customers = paginator.get_page(page_number)

        context = {
            'customers': customers,
            'search_query': search_query,
        }
        return render(request, 'dashboard/customers.html', context)


class CustomerDetailView(StaffRequiredMixin, View):
    """View customer details, team stats, and visual referral tree."""

    def get(self, request, user_id):
        customer = get_object_or_404(User, pk=user_id, is_staff=False)
        stats = get_referral_stats(customer)
        tree = build_referral_tree(customer)
        customer_bookings = Booking.objects.filter(user=customer).select_related('event').order_by('-created_at')

        context = {
            'customer': customer,
            'stats': stats,
            'tree': tree,
            'bookings': customer_bookings,
        }
        return render(request, 'dashboard/customer_detail.html', context)


class VendorListView(StaffRequiredMixin, View):
    """View to list and search event vendors."""

    def get(self, request):
        queryset = Vendor.objects.all().order_by('name')
        search_query = request.GET.get('search', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page')
        vendors = paginator.get_page(page_number)

        context = {
            'vendors': vendors,
            'search_query': search_query,
        }
        return render(request, 'dashboard/vendors.html', context)


class VendorCreateView(StaffRequiredMixin, View):
    """View to add a new vendor."""

    def get(self, request):
        form = VendorForm()
        return render(request, 'dashboard/vendor_form.html', {'form': form, 'action_title': 'Add New Vendor'})

    def post(self, request):
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            messages.success(request, f'Vendor "{vendor.name}" created successfully.')
            return redirect('dashboard-vendors')
        return render(request, 'dashboard/vendor_form.html', {'form': form, 'action_title': 'Add New Vendor'})


class VendorDetailView(StaffRequiredMixin, View):
    """View details of a vendor and their associated events."""

    def get(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        events = vendor.events.all().order_by('-start_datetime')
        return render(request, 'dashboard/vendor_detail.html', {'vendor': vendor, 'events': events})


class VendorUpdateView(StaffRequiredMixin, View):
    """View to update existing vendor information."""

    def get(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        form = VendorForm(instance=vendor)
        return render(request, 'dashboard/vendor_form.html', {'form': form, 'vendor': vendor, 'action_title': f'Edit {vendor.name}'})

    def post(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Vendor "{vendor.name}" updated successfully.')
            return redirect('dashboard-vendors')
        return render(request, 'dashboard/vendor_form.html', {'form': form, 'vendor': vendor, 'action_title': f'Edit {vendor.name}'})


class EventListView(StaffRequiredMixin, View):
    """View to list, search, and filter events."""

    def get(self, request):
        queryset = Event.objects.select_related('vendor').order_by('-start_datetime')
        search_query = request.GET.get('search', '').strip()
        vendor_filter = request.GET.get('vendor', '').strip()
        status_filter = request.GET.get('status', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(location__icontains=search_query)
            )

        if vendor_filter and vendor_filter.isdigit():
            queryset = queryset.filter(vendor_id=int(vendor_filter))

        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page')
        events = paginator.get_page(page_number)
        all_vendors = Vendor.objects.all().order_by('name')

        context = {
            'events': events,
            'vendors': all_vendors,
            'search_query': search_query,
            'vendor_filter': vendor_filter,
            'status_filter': status_filter,
        }
        return render(request, 'dashboard/events.html', context)


class EventCreateView(StaffRequiredMixin, View):
    """View to add a new event."""

    def get(self, request):
        form = EventForm()
        return render(request, 'dashboard/event_form.html', {'form': form, 'action_title': 'Add New Event'})

    def post(self, request):
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            messages.success(request, f'Event "{event.title}" created successfully.')
            return redirect('dashboard-events')
        return render(request, 'dashboard/event_form.html', {'form': form, 'action_title': 'Add New Event'})


class EventUpdateView(StaffRequiredMixin, View):
    """View to edit an existing event."""

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)
        form = EventForm(instance=event)
        return render(request, 'dashboard/event_form.html', {'form': form, 'event': event, 'action_title': f'Edit {event.title}'})

    def post(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f'Event "{event.title}" updated successfully.')
            return redirect('dashboard-events')
        return render(request, 'dashboard/event_form.html', {'form': form, 'event': event, 'action_title': f'Edit {event.title}'})


class BookingListView(StaffRequiredMixin, View):
    """View for staff to view and filter customer bookings."""

    def get(self, request):
        queryset = Booking.objects.select_related('user', 'event', 'event__vendor').order_by('-created_at')
        status_filter = request.GET.get('status', '').strip()

        if status_filter in ['CONFIRMED', 'CANCELLED']:
            queryset = queryset.filter(status=status_filter)

        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page')
        bookings = paginator.get_page(page_number)

        context = {
            'bookings': bookings,
            'status_filter': status_filter,
        }
        return render(request, 'dashboard/bookings.html', context)
