from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from events.models import Event, Vendor


class StaffLoginForm(forms.Form):
    """Form for staff authentication into the custom dashboard."""
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'staff@quickbook.com'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'})
    )


class VendorForm(forms.ModelForm):
    """Form for creating and editing vendors."""

    class Meta:
        model = Vendor
        fields = ['name', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Vendor or Organizer Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@vendor.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Venue / Business Address'}),
        }


class EventForm(forms.ModelForm):
    """Form for creating and editing events in the staff dashboard."""

    class Meta:
        model = Event
        fields = [
            'vendor',
            'title',
            'description',
            'location',
            'start_datetime',
            'end_datetime',
            'total_seats',
            'available_seats',
            'is_active',
        ]
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Event Description'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Venue / Location'}),
            'start_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'total_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'available_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On new event creation, available_seats can be left blank to default to total_seats
        if not self.instance.pk:
            self.fields['available_seats'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        total = cleaned_data.get('total_seats')
        available = cleaned_data.get('available_seats')

        if start and end and end < start:
            self.add_error('end_datetime', 'End date and time cannot be earlier than start date and time.')

        if total is not None and total <= 0:
            self.add_error('total_seats', 'Total seats must be a positive integer greater than zero.')

        if available is not None and total is not None:
            if available < 0:
                self.add_error('available_seats', 'Available seats cannot be negative.')
            elif available > total:
                self.add_error('available_seats', 'Available seats cannot exceed total seats.')

        return cleaned_data
