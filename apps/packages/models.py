"""
Package and subscription models.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Package(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    logo = models.URLField(max_length=500, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    icon = models.URLField(max_length=500, null=True, blank=True)
    period_days = models.PositiveIntegerField(null=True, blank=True)
    number_of_questions = models.PositiveIntegerField(null=True, blank=True)
    trial_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='packages'
    )
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    DIFFICULTY_CHOICES = {
        BEGINNER: _('Beginner'),
        INTERMEDIATE: _('Intermediate'),
        ADVANCED: _('Advanced'),
    }

    is_trial = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    language = models.CharField(max_length=50, null=True, blank=True)
    difficulty_level = models.PositiveSmallIntegerField(
        choices=list(DIFFICULTY_CHOICES.items()),
        null=True,
        blank=True,
    )
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    students_count = models.PositiveIntegerField(default=0)
    discount_percentage = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'packages'
        verbose_name = _('Package')
        verbose_name_plural = _('Packages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_trial', 'status']),
        ]

    def __str__(self):
        return self.name


class UserPackage(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_packages'
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        db_column='package_id',
        related_name='subscriptions'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    price_before_discount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    pay_id = models.IntegerField(null=True, blank=True)
    subscription_status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_packages'
        verbose_name = _('User Package')
        verbose_name_plural = _('User Packages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
            models.Index(fields=['user', 'subscription_status']),
        ]

    @property
    def is_active(self):
        from django.utils import timezone
        return (
            self.subscription_status == self.ACTIVE
            and self.end_date
            and self.end_date >= timezone.now().date()
        )


class DiscountCode(models.Model):
    TYPE_PERCENTAGE = 1
    TYPE_AMOUNT = 2
    TYPE_CHOICES = [
        (TYPE_PERCENTAGE, _('Percentage')),
        (TYPE_AMOUNT, _('Amount')),
    ]

    STATUS_ACTIVE = 1
    STATUS_INACTIVE = 2
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Active')),
        (STATUS_INACTIVE, _('Inactive')),
    ]

    code = models.CharField(max_length=255, unique=True)
    marketer = models.CharField(max_length=255)
    type = models.IntegerField(choices=TYPE_CHOICES)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    quantity = models.IntegerField()
    used_count = models.PositiveIntegerField(default=0)
    from_date = models.DateField()
    to_date = models.DateField()
    status = models.IntegerField(choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'discounts_codes'
        verbose_name = _('Discount Code')
        verbose_name_plural = _('Discount Codes')
        indexes = [
            models.Index(fields=['status', 'from_date', 'to_date']),
        ]

    def is_valid(self):
        from django.utils import timezone
        return (
            self.status == self.STATUS_ACTIVE
            and self.from_date <= timezone.now().date() <= self.to_date
            and self.used_count < self.quantity
        )
