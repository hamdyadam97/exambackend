from datetime import timedelta
from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.core.admin_site import admin_site
from apps.packages.models import (
    Package, UserPackage, DiscountCode,
)


class PackageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'price', 'period_days',
        'subscription_count',
        'status', 'is_featured', 'is_bestseller', 'is_new', 'created_at',
    ]
    list_filter = [
        'status', 'is_trial', 'is_featured', 'is_bestseller', 'is_new',
        'category', 'difficulty_level', 'language', 'created_at',
    ]
    search_fields = ['name', 'description', 'code']
    autocomplete_fields = ['category']
    list_select_related = ['category']
    date_hierarchy = 'created_at'
    actions = ['activate', 'deactivate', 'mark_featured', 'unmark_featured']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            subscription_count=Count('subscriptions'),
        )

    @admin.display(description=_('Subscriptions'))
    def subscription_count(self, obj):
        return obj.subscription_count

    @admin.action(description=_('Activate selected packages'))
    def activate(self, request, queryset):
        queryset.update(status=Package.ACTIVE)

    @admin.action(description=_('Deactivate selected packages'))
    def deactivate(self, request, queryset):
        queryset.update(status=Package.INACTIVE)

    @admin.action(description=_('Mark selected packages as featured'))
    def mark_featured(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description=_('Remove featured flag from selected packages'))
    def unmark_featured(self, request, queryset):
        queryset.update(is_featured=False)



admin_site.register(Package, PackageAdmin)
class UserPackageAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'package', 'start_date', 'end_date',
        'subscription_status', 'is_active_display', 'created_at',
    ]
    list_filter = ['subscription_status', 'start_date', 'end_date', 'created_at']
    search_fields = ['user__phone', 'package__name']
    autocomplete_fields = ['user', 'package']
    list_select_related = ['user', 'package']
    date_hierarchy = 'created_at'
    actions = ['activate_subscriptions', 'cancel_subscriptions', 'extend_30_days']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    @admin.display(description=_('Active'), boolean=True)
    def is_active_display(self, obj):
        return obj.is_active

    @admin.action(description=_('Activate selected subscriptions'))
    def activate_subscriptions(self, request, queryset):
        queryset.update(subscription_status=UserPackage.ACTIVE)

    @admin.action(description=_('Cancel selected subscriptions'))
    def cancel_subscriptions(self, request, queryset):
        queryset.update(subscription_status=UserPackage.INACTIVE)

    @admin.action(description=_('Extend selected subscriptions by 30 days'))
    def extend_30_days(self, request, queryset):
        for subscription in queryset:
            current_end = subscription.end_date or timezone.now().date()
            subscription.end_date = current_end + timedelta(days=30)
            subscription.save(update_fields=['end_date'])



admin_site.register(UserPackage, UserPackageAdmin)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'marketer', 'type', 'percentage', 'amount',
        'used_count', 'quantity', 'status', 'is_valid_display',
        'from_date', 'to_date',
    ]
    list_filter = ['type', 'status', 'from_date', 'to_date']
    search_fields = ['code', 'marketer']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['activate', 'deactivate', 'reset_used_count']

    @admin.display(description=_('Valid Now'), boolean=True)
    def is_valid_display(self, obj):
        return obj.is_valid()

    @admin.action(description=_('Activate selected discount codes'))
    def activate(self, request, queryset):
        queryset.update(status=DiscountCode.STATUS_ACTIVE)

    @admin.action(description=_('Deactivate selected discount codes'))
    def deactivate(self, request, queryset):
        queryset.update(status=DiscountCode.STATUS_INACTIVE)

    @admin.action(description=_('Reset used count for selected codes'))
    def reset_used_count(self, request, queryset):
        queryset.update(used_count=0)

admin_site.register(DiscountCode, DiscountCodeAdmin)
