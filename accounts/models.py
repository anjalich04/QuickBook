import secrets
import string
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def generate_referral_code(length=8):
    """Generate a random alphanumeric uppercase referral code."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


class CustomUserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        
        # Ensure referral_code is generated if not provided
        if not extra_fields.get('referral_code'):
            extra_fields['referral_code'] = self._generate_unique_referral_code()

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def _generate_unique_referral_code(self):
        while True:
            code = generate_referral_code()
            if not self.model.objects.filter(referral_code=code).exists():
                return code


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model supporting email login, binary referral placement, and referral trees."""

    class ReferralPosition(models.TextChoices):
        LEFT = 'LEFT', 'Left'
        RIGHT = 'RIGHT', 'Right'

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    referral_code = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    
    # Binary tree parent
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    # Position under binary parent (LEFT or RIGHT)
    referral_position = models.CharField(
        max_length=10,
        choices=ReferralPosition.choices,
        null=True,
        blank=True,
        db_index=True
    )
    # Original inviter / sponsor who shared the referral code
    sponsor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sponsored_users'
    )
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['-date_joined']
        constraints = [
            models.UniqueConstraint(
                fields=['referred_by', 'referral_position'],
                name='unique_parent_referral_position',
                condition=models.Q(referred_by__isnull=False) & models.Q(referral_position__isnull=False)
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def left_child(self):
        return self.referrals.filter(referral_position=self.ReferralPosition.LEFT).first()

    @property
    def right_child(self):
        return self.referrals.filter(referral_position=self.ReferralPosition.RIGHT).first()

    def clean(self):
        super().clean()
        if self.referred_by and self.referred_by_id == self.id:
            raise ValidationError('A user cannot refer themselves.')

    def save(self, *args, **kwargs):
        if not self.referral_code:
            while True:
                code = generate_referral_code()
                if not User.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)
