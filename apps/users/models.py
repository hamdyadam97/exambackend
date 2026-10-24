"""
User models.
Uses Django's built-in auth framework with custom user model.
"""
import hashlib
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.users.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {
        ACTIVE: _('Active'),
        INACTIVE: _('Inactive'),
    }

    ROLE_ADMIN = 1
    ROLE_USER = 2
    ROLE_ACCOUNTANT = 3
    ROLE_DATA_ENTRY = 4

    ROLE_CHOICES = {
        ROLE_ADMIN: _('Admin'),
        ROLE_USER: _('User'),
        ROLE_ACCOUNTANT: _('Accountant'),
        ROLE_DATA_ENTRY: _('Data Entry'),
    }

    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True, unique=True)
    is_email_verified = models.BooleanField(default=False)

    # Phone fields consolidated
    phone = models.CharField(max_length=20, null=True, blank=True, unique=True)
    phone_country_code = models.CharField(max_length=10, null=True, blank=True)
    is_phone_verified = models.BooleanField(default=False)

    thumb = models.URLField(max_length=500, null=True, blank=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    score = models.IntegerField(default=0, null=True, blank=True)

    role_type = models.IntegerField(choices=list(ROLE_CHOICES.items()), default=ROLE_USER)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)

    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['status', 'role_type']),
        ]

    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.phone or self.email or str(self.id)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @property
    def is_active_user(self):
        return self.status == self.ACTIVE and self.deleted_at is None

    def is_admin(self):
        return self.role_type == self.ROLE_ADMIN or self.is_superuser

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def subscriptions(self):
        return self.user_packages.all()

    def active_subscriptions(self):
        return self.user_packages.filter(
            subscription_status=1,
            end_date__gte=timezone.now().date()
        )

    def make_trial_subscription(self):
        from django.apps import apps
        Package = apps.get_model('packages', 'Package')
        UserPackage = apps.get_model('packages', 'UserPackage')
        package = Package.objects.filter(is_trial=True).first()
        if package:
            has_trial = UserPackage.objects.filter(user=self, package=package).exists()
            if not has_trial:
                UserPackage.objects.create(
                    user=self,
                    package=package,
                    start_date=timezone.now().date(),
                    end_date=timezone.now().date() + timezone.timedelta(days=int(package.period_days or 0)),
                )

    def subscribed_categories(self):
        """Return active category tree the user is subscribed to."""
        from apps.content.models import Category
        return Category.objects.filter(
            packages__subscriptions__user=self,
            packages__subscriptions__subscription_status=1,
            packages__subscriptions__end_date__gte=timezone.now().date(),
            level=Category.LEVEL_CATEGORY
        ).distinct()

    def subscribed_sub_categories(self):
        """Return active sub-categories from user's subscriptions."""
        from apps.content.models import Category
        direct = Category.objects.filter(
            packages__subscriptions__user=self,
            packages__subscriptions__subscription_status=1,
            packages__subscriptions__end_date__gte=timezone.now().date(),
            level=Category.LEVEL_SUB_CATEGORY
        ).distinct()
        if direct.exists():
            return direct
        # Fallback: all sub-categories under subscribed categories
        category_ids = self.subscribed_categories().values_list('id', flat=True)
        return Category.objects.filter(parent_id__in=category_ids, level=Category.LEVEL_SUB_CATEGORY)

    def subscribed_sub_sub_categories(self):
        """Return active sub-sub-categories under subscribed sub-categories."""
        from apps.content.models import Category
        from django.db.models import Count
        sub_ids = self.subscribed_sub_categories().values_list('id', flat=True)
        return Category.objects.filter(
            parent_id__in=sub_ids,
            level=Category.LEVEL_SUB_SUB_CATEGORY
        ).annotate(questions_count=Count('questions_as_sub_sub'))


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        db_column='user_id'
    )
    specialization = models.CharField(max_length=255, null=True, blank=True)
    governorate = models.CharField(max_length=255, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    profile_completed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')


class OtpRequest(models.Model):
    """
    Stores OTP requests. The OTP itself is stored as a SHA-256 hash
    to avoid storing plaintext codes in the database.
    """
    phone = models.CharField(max_length=20, db_index=True)
    otp_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'otp_requests'
        verbose_name = _('OTP Request')
        verbose_name_plural = _('OTP Requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', '-created_at']),
        ]

    def set_otp(self, otp: str):
        self.otp_hash = hashlib.sha256(otp.encode()).hexdigest()

    def verify(self, otp: str) -> bool:
        if timezone.now() > self.expires_at:
            return False
        return hashlib.sha256(otp.encode()).hexdigest() == self.otp_hash

    def is_expired(self):
        return timezone.now() > self.expires_at


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reset_tokens',
        db_column='user_id'
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = _('Password Reset Token')
        verbose_name_plural = _('Password Reset Tokens')


class AuditLog(models.Model):
    """
    Generic audit log for sensitive operations (payments, admin changes, etc.)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_column='user_id'
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['action', '-created_at']),
        ]

