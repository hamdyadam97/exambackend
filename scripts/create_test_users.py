import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User

USERS = [
    {
        'phone': '+962790000001',
        'first_name': 'Admin',
        'last_name': 'User',
        'role_type': User.ROLE_ADMIN,
        'is_staff': True,
        'is_superuser': True,
        'is_phone_verified': True,
        'password': 'admin123',
    },
    {
        'phone': '+962790000002',
        'first_name': 'Regular',
        'last_name': 'User',
        'role_type': User.ROLE_USER,
        'is_phone_verified': True,
        'password': 'user123',
    },
    {
        'phone': '+962790000003',
        'first_name': 'Accountant',
        'last_name': 'User',
        'role_type': User.ROLE_ACCOUNTANT,
        'is_staff': True,
        'is_phone_verified': True,
        'password': 'accountant123',
    },
    {
        'phone': '+962790000004',
        'first_name': 'Data Entry',
        'last_name': 'User',
        'role_type': User.ROLE_DATA_ENTRY,
        'is_staff': True,
        'is_phone_verified': True,
        'password': 'dataentry123',
    },
]


def main():
    for data in USERS:
        password = data.pop('password')
        user, created = User.objects.update_or_create(phone=data['phone'], defaults=data)
        user.set_password(password)
        user.save()
        print(f"{'Created' if created else 'Updated'}: {user.phone} ({user.get_role_type_display()})")


if __name__ == '__main__':
    main()
