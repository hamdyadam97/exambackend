from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.core.admin_site import admin_site
from apps.payments.models import (
    PaymentType, PaymentTransaction, MoneyLog, PaymentCardToken, Invoice,
)


class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name']
    date_hierarchy = 'created_at'
    actions = ['activate', 'deactivate']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Activate selected payment types'))
    def activate(self, request, queryset):
        queryset.update(status=PaymentType.ACTIVE)

    @admin.action(description=_('Deactivate selected payment types'))
    def deactivate(self, request, queryset):
        queryset.update(status=PaymentType.INACTIVE)



admin_site.register(PaymentType, PaymentTypeAdmin)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'package', 'amount', 'currency', 'is_success',
        'transaction_type', 'payment_id', 'created_at',
    ]
    list_filter = ['is_success', 'transaction_type', 'currency', 'created_at']
    search_fields = ['user__phone', 'payment_id', 'gateway_transaction_id', 'coupon_code']
    autocomplete_fields = ['user', 'package']
    list_select_related = ['user', 'package']
    date_hierarchy = 'created_at'
    actions = ['mark_success', 'mark_failed']
    readonly_fields = [
        'user', 'package', 'transaction_type', 'payment_id', 'payment_brand',
        'gateway_transaction_id', 'amount', 'currency', 'result_summary',
        'coupon_code', 'created_at', 'updated_at',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request)

    @admin.action(description=_('Mark selected transactions as successful'))
    def mark_success(self, request, queryset):
        queryset.update(is_success=True)

    @admin.action(description=_('Mark selected transactions as failed'))
    def mark_failed(self, request, queryset):
        queryset.update(is_success=False)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response
        totals = qs.aggregate(total=Sum('amount'))
        response.context_data['title'] += _(
            ' | Visible total: %(total)s' % {'total': totals['total'] or 0}
        )
        return response



admin_site.register(PaymentTransaction, PaymentTransactionAdmin)
class MoneyLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'item', 'payment_id', 'status', 'created_at']
    list_filter = ['platform', 'status', 'created_at']
    search_fields = ['user__phone', 'payment_id']
    autocomplete_fields = ['user', 'item']
    list_select_related = ['user', 'item']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(MoneyLog, MoneyLogAdmin)
class PaymentCardTokenAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'last4', 'brand', 'expiry_month',
        'expiry_year', 'is_active', 'created_at',
    ]
    list_filter = ['is_active', 'brand', 'created_at']
    search_fields = ['user__phone', 'last4']
    autocomplete_fields = ['user']
    readonly_fields = ['token', 'created_at', 'updated_at']
    actions = ['activate', 'deactivate']

    @admin.action(description=_('Activate selected card tokens'))
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description=_('Deactivate selected card tokens'))
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)



admin_site.register(PaymentCardToken, PaymentCardTokenAdmin)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'user', 'user_package', 'total_amount',
        'status', 'sent_to_accounting', 'created_at',
    ]
    list_filter = ['status', 'sent_to_accounting', 'created_at']
    search_fields = ['invoice_number', 'user__phone']
    autocomplete_fields = ['user', 'user_package', 'created_by', 'sent_by']
    list_select_related = ['user', 'user_package', 'created_by', 'sent_by']
    date_hierarchy = 'created_at'
    actions = ['mark_paid', 'mark_sent_to_accounting']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Mark selected invoices as paid'))
    def mark_paid(self, request, queryset):
        queryset.update(status=Invoice.STATUS_PAID)

    @admin.action(description=_('Mark selected invoices as sent to accounting'))
    def mark_sent_to_accounting(self, request, queryset):
        queryset.update(
            sent_to_accounting=True,
            sent_by=request.user,
            sent_at=timezone.now(),
        )

admin_site.register(Invoice, InvoiceAdmin)
