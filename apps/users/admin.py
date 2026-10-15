import csv
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from apps.core.admin_site import admin_site
from apps.users.models import User, UserProfile, OtpRequest, PasswordResetToken, AuditLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _('Profile')
    readonly_fields = ['created_at', 'updated_at']


class UserAdmin(BaseUserAdmin):
    list_display = [
        'phone', 'full_name', 'email', 'role_type', 'status',
        'is_phone_verified', 'is_email_verified', 'is_active_display',
        'is_staff', 'date_joined',
    ]
    list_filter = [
        'role_type', 'status', 'is_staff', 'is_superuser',
        'is_phone_verified', 'is_email_verified', 'date_joined',
    ]
    search_fields = ['phone', 'first_name', 'last_name', 'email']
    ordering = ['-date_joined']
    date_hierarchy = 'date_joined'
    list_per_page = 50
    inlines = [UserProfileInline]
    filter_horizontal = ('groups', 'user_permissions')
    readonly_fields = ['date_joined', 'deleted_at']
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Verification'), {'fields': ('is_phone_verified', 'is_email_verified')}),
        (_('Permissions'), {
            'fields': ('role_type', 'status', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('date_joined', 'deleted_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2', 'role_type'),
        }),
    )
    actions = ['verify_phone', 'verify_email', 'activate_users', 'deactivate_users', 'export_to_csv']

    @admin.display(description=_('Active'), boolean=True)
    def is_active_display(self, obj):
        return obj.is_active_user

    @admin.action(description=_('Verify phone number for selected users'))
    def verify_phone(self, request, queryset):
        queryset.update(is_phone_verified=True)

    @admin.action(description=_('Verify email for selected users'))
    def verify_email(self, request, queryset):
        queryset.update(is_email_verified=True)

    @admin.action(description=_('Activate selected users'))
    def activate_users(self, request, queryset):
        queryset.update(status=User.ACTIVE)

    @admin.action(description=_('Deactivate selected users'))
    def deactivate_users(self, request, queryset):
        queryset.update(status=User.INACTIVE)

    @admin.action(description=_('Export selected users to CSV'))
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Phone', 'First Name', 'Last Name', 'Email',
            'Role', 'Status', 'Phone Verified', 'Email Verified', 'Joined At',
        ])
        for user in queryset.iterator():
            writer.writerow([
                user.id, user.phone, user.first_name, user.last_name,
                user.email, user.get_role_type_display(), user.get_status_display(),
                user.is_phone_verified, user.is_email_verified, user.date_joined,
            ])
        return response


admin_site.register(User, UserAdmin)


class OtpRequestAdmin(admin.ModelAdmin):
    list_display = ['phone', 'attempts', 'expires_at', 'verified', 'created_at']
    list_filter = ['verified', 'created_at']
    search_fields = ['phone']
    readonly_fields = ['otp_hash', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    actions = ['mark_verified']

    @admin.action(description=_('Mark selected OTP requests as verified'))
    def mark_verified(self, request, queryset):
        queryset.update(verified=True)


admin_site.register(OtpRequest, OtpRequestAdmin)


class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'used', 'expires_at', 'created_at']
    list_filter = ['used', 'created_at']
    search_fields = ['user__phone', 'user__email']
    readonly_fields = ['token_hash', 'created_at']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['user']


admin_site.register(PasswordResetToken, PasswordResetTokenAdmin)


class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'entity_type', 'entity_id', 'user', 'created_at']
    list_filter = ['action', 'entity_type', 'created_at']
    search_fields = ['entity_type', 'entity_id', 'user__phone']
    readonly_fields = [
        'action', 'entity_type', 'entity_id', 'metadata',
        'ip_address', 'user', 'created_at',
    ]
    date_hierarchy = 'created_at'
    autocomplete_fields = ['user']


admin_site.register(AuditLog, AuditLogAdmin)
