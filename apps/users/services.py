"""
User domain services.
"""
import hashlib
import logging
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User, UserProfile, OtpRequest, PasswordResetToken, AuditLog

logger = logging.getLogger('api')


class OtpService:
    """Handles OTP generation, storage (hashed), verification, and rate limiting."""

    MAX_ATTEMPTS = 3
    EXPIRY_MINUTES = 20

    @classmethod
    def generate(cls, phone: str, ip_address=None):
        from django.utils.crypto import get_random_string
        otp = get_random_string(length=6, allowed_chars='0123456789')
        expires_at = timezone.now() + timezone.timedelta(minutes=cls.EXPIRY_MINUTES)
        request = OtpRequest.objects.create(
            phone=phone,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        request.set_otp(otp)
        request.save(update_fields=['otp_hash'])
        return otp

    @classmethod
    def verify(cls, phone: str, otp: str):
        latest = OtpRequest.objects.filter(phone=phone, verified=False).order_by('-created_at').first()
        if not latest:
            return False, 'No OTP request found'
        if latest.is_expired():
            return False, 'OTP expired'
        if latest.attempts >= cls.MAX_ATTEMPTS:
            return False, 'Too many attempts'
        latest.attempts += 1
        latest.save(update_fields=['attempts'])
        if not latest.verify(otp):
            return False, 'Invalid OTP'
        latest.verified = True
        latest.save(update_fields=['verified'])
        return True, 'Verified'

    @classmethod
    def can_resend(cls, phone: str) -> bool:
        latest = OtpRequest.objects.filter(phone=phone).order_by('-created_at').first()
        if not latest:
            return True
        return latest.created_at < timezone.now() - timezone.timedelta(minutes=1)


class UserService:
    """Handles user registration, authentication, and profile management."""

    @classmethod
    def signup(cls, data, ip_address=None):
        with transaction.atomic():
            user = User.objects.create(
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data['phone'],
                phone_country_code=data.get('phone_country_code'),
                email=data.get('email'),
            )
            user.set_password(data['password'])
            user.save()
            UserProfile.objects.create(
                user=user,
                specialization=data.get('specialization', ''),
                governorate=data.get('governorate', ''),
                birth_date=data.get('birth_date'),
                profile_completed=True,
            )
            otp = OtpService.generate(user.phone, ip_address)
            return user, otp

    @classmethod
    def verify_otp(cls, phone: str, otp: str):
        ok, msg = OtpService.verify(phone, otp)
        if not ok:
            return None, msg
        user = User.objects.get(phone=phone)
        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])
        user.make_trial_subscription()
        return user, 'Verified'

    @classmethod
    def login(cls, phone: str, password: str):
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return None, 'Invalid credentials'
        if not check_password(password, user.password):
            return None, 'Invalid credentials'
        return user, 'OK'

    @classmethod
    def reset_password(cls, phone: str, password: str):
        user = User.objects.get(phone=phone)
        user.set_password(password)
        user.is_phone_verified = True
        user.save()
        return user

    @classmethod
    def update_profile(cls, user: User, data: dict):
        for field in ['first_name', 'last_name', 'email', 'phone_country_code']:
            if field in data:
                setattr(user, field, data[field])
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field in ['specialization', 'governorate', 'birth_date']:
            if field in data:
                setattr(profile, field, data[field])
        profile.save()
        return user

    @classmethod
    def get_tokens(cls, user: User):
        refresh = RefreshToken.for_user(user)
        return {
            'token': str(refresh.access_token),
            'token_expired_at': timezone.now() + refresh.access_token.lifetime,
            'refresh': str(refresh),
        }


class AuditService:
    """Simple audit logging helper."""

    @classmethod
    def log(cls, action, entity_type, entity_id=None, user=None, metadata=None, ip_address=None):
        return AuditLog.objects.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user=user,
            metadata=metadata or {},
            ip_address=ip_address,
        )
