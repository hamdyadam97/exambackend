"""
Payment related models.

Security note:
- We do NOT store raw card numbers, CVV, or full card data.
- Payment tokens are provided by the payment gateway (e.g. HyperPay) and
  should be treated as opaque identifiers.
- For PCI compliance, prefer a certified vault or the gateway's tokenization.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class PaymentType(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    name = models.CharField(max_length=255)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_types'
        verbose_name = _('Payment Type')
        verbose_name_plural = _('Payment Types')

    def __str__(self):
        return self.name


class PaymentTransaction(models.Model):
    """
    Stores payment gateway responses.
    Sensitive fields (card, customer, custom_parameters) are stored as JSON
    only if absolutely required for debugging; in production they should be
    omitted or masked.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='payment_transactions'
    )
    package = models.ForeignKey(
        'packages.Package',
        on_delete=models.SET_NULL,
        db_column='item_id',
        related_name='payment_transactions',
        null=True,
        blank=True
    )
    transaction_type = models.CharField(max_length=20, db_column='type')
    payment_id = models.CharField(max_length=100, db_index=True)
    payment_brand = models.CharField(max_length=50, null=True, blank=True)
    gateway_transaction_id = models.CharField(max_length=100, db_column='transaction_id', null=True, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    result_summary = models.JSONField(default=dict, blank=True)
    is_success = models.BooleanField(default=False)
    coupon_code = models.CharField(max_length=255, null=True, blank=True, db_column='coupon')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hyperpay_results'
        verbose_name = _('Payment Transaction')
        verbose_name_plural = _('Payment Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['coupon_code']),
        ]


class MoneyLog(models.Model):
    PLATFORM_WEB = 'web'
    PLATFORM_MOBILE = 'mobile'
    PLATFORM_IOS = 'ios'
    PLATFORM_ANDROID = 'android'
    PLATFORM_CHOICES = [
        (PLATFORM_WEB, _('Web')),
        (PLATFORM_MOBILE, _('Mobile')),
        (PLATFORM_IOS, _('iOS')),
        (PLATFORM_ANDROID, _('Android')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='money_logs',
        null=True,
        blank=True
    )
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    item = models.ForeignKey(
        'packages.Package',
        on_delete=models.SET_NULL,
        db_column='item_id',
        related_name='money_logs',
        null=True,
        blank=True
    )
    unique_id = models.CharField(max_length=50, null=True, blank=True)
    payment_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.IntegerField()
    coupon_code = models.CharField(max_length=255, null=True, blank=True, db_column='coupon')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'money_logs'
        verbose_name = _('Money Log')
        verbose_name_plural = _('Money Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['user', '-created_at']),
        ]


class Invoice(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_PAID = 'paid'
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_SENT, _('Sent')),
        (STATUS_PAID, _('Paid')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='invoices'
    )
    user_package = models.ForeignKey(
        'packages.UserPackage',
        on_delete=models.CASCADE,
        db_column='user_package_id',
        related_name='invoice'
    )
    invoice_number = models.CharField(max_length=255, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sent_to_accounting = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column='created_by',
        related_name='created_invoices',
        null=True,
        blank=True
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        db_column='sent_by',
        related_name='sent_invoices',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        ordering = ['-created_at']


class PaymentCardToken(models.Model):
    """
    Minimal reference to a payment card token issued by the gateway.
    The actual sensitive data is held by the payment provider.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='payment_card_tokens'
    )
    token = models.CharField(max_length=255, db_index=True)
    last4 = models.CharField(max_length=4)
    brand = models.CharField(max_length=50, null=True, blank=True)
    expiry_month = models.PositiveSmallIntegerField()
    expiry_year = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users_credit_cards'
        verbose_name = _('Payment Card Token')
        verbose_name_plural = _('Payment Card Tokens')
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
