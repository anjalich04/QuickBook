from django.contrib import admin
from .models import Booking, Event, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'phone')
    ordering = ('name',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'vendor', 'start_datetime', 'end_datetime', 'total_seats', 'available_seats', 'is_active')
    list_filter = ('is_active', 'vendor', 'start_datetime')
    search_fields = ('title', 'location', 'vendor__name')
    ordering = ('-start_datetime',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event', 'quantity', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'event__title')
    ordering = ('-created_at',)
