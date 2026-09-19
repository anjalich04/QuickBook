from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers
from .models import User
from .services import find_available_binary_placement


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying user details."""
    referred_by_code = serializers.CharField(
        source='referred_by.referral_code', read_only=True, default=None
    )
    sponsor_code = serializers.CharField(
        source='sponsor.referral_code', read_only=True, default=None
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'referral_code',
            'referral_position',
            'referred_by_code',
            'sponsor_code',
            'is_staff',
            'date_joined',
        ]
        read_only_fields = [
            'id',
            'referral_code',
            'referral_position',
            'referred_by_code',
            'sponsor_code',
            'is_staff',
            'date_joined',
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration with automatic binary referral placement."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=6,
        style={'input_type': 'password'}
    )
    referral_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text='Optional referral code of the inviting user.'
    )

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'first_name',
            'last_name',
            'referral_code',
        ]
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate_email(self, value):
        normalized_email = value.lower()
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return normalized_email

    def validate_referral_code(self, value):
        if value:
            code = value.strip().upper()
            sponsor = User.objects.filter(referral_code=code, is_active=True).first()
            if not sponsor:
                raise serializers.ValidationError('Invalid referral code. No matching active user found.')
            return code
        return None

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        referral_code = attrs.get('referral_code')
        if referral_code:
            sponsor = User.objects.filter(referral_code=referral_code).first()
            if sponsor and sponsor.email.lower() == email:
                raise serializers.ValidationError({'referral_code': 'A user cannot refer themselves.'})
        return attrs

    def create(self, validated_data):
        referral_code = validated_data.pop('referral_code', None)
        parent = None
        position = None
        sponsor = None

        with transaction.atomic():
            if referral_code:
                sponsor = User.objects.filter(referral_code=referral_code).first()
                if sponsor:
                    parent, position = find_available_binary_placement(sponsor)

            user = User.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                referred_by=parent,
                referral_position=position,
                sponsor=sponsor,
            )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for authenticating users via email and password."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError('Both email and password are required.')

        user = authenticate(
            request=self.context.get('request'),
            email=email,
            password=password
        )

        if not user:
            raise serializers.ValidationError('Invalid email or password.')

        if not user.is_active:
            raise serializers.ValidationError('This user account is inactive.')

        attrs['user'] = user
        return attrs
