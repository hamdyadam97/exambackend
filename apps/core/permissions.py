"""
Custom permission classes.
"""
from rest_framework import permissions
from apps.users.models import User


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.role_type == User.ROLE_ADMIN or request.user.is_superuser)
        )


class IsUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role_type == User.ROLE_USER
        )


class IsAccountant(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role_type == User.ROLE_ACCOUNTANT
        )


class IsDataEntry(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role_type == User.ROLE_DATA_ENTRY
        )


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsOwner(permissions.BasePermission):
    """Object-level permission allowing only owners of an object."""

    owner_field = 'user'

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, self.owner_field, None)
        return owner == request.user


class IsAdminOrOwner(permissions.BasePermission):
    """Admin can access anything; regular users can access only their own."""

    owner_field = 'user'

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role_type == User.ROLE_ADMIN or request.user.is_superuser:
            return True
        owner = getattr(obj, self.owner_field, None)
        return owner == request.user


class HasPermission(permissions.BasePermission):
    """Permission based on a named permission map (legacy compatibility)."""

    permission_map = {
        'user_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'appinfo_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'billing_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT],
        'package_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'userpackage_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'discountcode_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'payment_type_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'category_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'subcategory_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'sub_subcategory_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'topic_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'exam_section_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'exam_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'question_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'examquestion_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'userexam_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'notification_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'ai_instruction_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'blog_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'lab_value_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'categories_export_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
        'testimonial_access': [User.ROLE_ADMIN, User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY],
    }

    def __init__(self, permission):
        self.permission = permission

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        allowed_roles = self.permission_map.get(self.permission, [])
        return request.user.role_type in allowed_roles or request.user.is_superuser
