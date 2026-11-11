"""
User API views.
"""
import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from apps.users.models import User, UserProfile
from apps.users.serializers import (
    UserResource, UserLoginSerializer, UserSignupSerializer,
    VerifyOtpSerializer, ForgetPasswordSerializer, ResetPasswordSerializer,
    UpdateProfileSerializer, UpdatePasswordSerializer,
)
from apps.core.utils import api_response, send_response, send_error, api_get, api_post, rearrange_tele_input_data
from apps.users.services import OtpService, PasswordResetService
from apps.core.auth import login_response, logout_response, session_payload
from apps.users.throttling import client_ip, is_throttled, register_failed_attempt, clear_attempts

logger = logging.getLogger('api')


class SmsNotSent(Exception):
    """The SMS gateway did not accept the verification code."""


def _mask_phone(phone):
    """Keep only the last 3 digits for diagnostics; never log full numbers."""
    if not phone:
        return ''
    return '*' * max(len(str(phone)) - 3, 0) + str(phone)[-3:]


def _log_failed_login(request, phone):
    masked = _mask_phone(phone)
    ip = request.META.get('REMOTE_ADDR')
    logger.info(
        'Failed login attempt (phone=%s, ip=%s)',
        masked,
        ip,
        extra={
            'path': request.path,
            'method': request.method,
            'phone': masked,
            'ip': ip,
        },
    )


class BaseApiView(APIView):
    pass


def _phone_from(data):
    """The phone from a request body: `phone`, `mobile` (what the web app sends), or dial_code + mobile_number."""
    if data.get('mobile_number'):
        return rearrange_tele_input_data(data.copy()).get('phone', '')
    return str(data.get('phone') or data.get('mobile') or '').strip()


def _verify_otp_request(request):
    """Check the OTP in the request; returns (user, None) on success or (None, error response)."""
    serializer = VerifyOtpSerializer(data={'phone': _phone_from(request.data), 'otp': request.data.get('otp')})
    if not serializer.is_valid():
        return None, send_error('Validation Errors', serializer.errors, 422)

    user = User.objects.filter(phone=serializer.validated_data['phone']).first()
    if not user:
        return None, send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

    ok, message = OtpService.verify(user.phone, serializer.validated_data['otp'])
    if not ok:
        status = 429 if message == 'Too many attempts' else 422
        return None, send_error('Validation Errors', {'otp': [message]}, status)
    return user, None


def signed_in_response(request, message, user):
    """Success response that starts a session: the token is set as an httpOnly cookie, never in the body."""
    response = send_response(message, {
        **session_payload(user),
        'user': UserResource(user, context={'request': request}).data,
    })
    return login_response(response, user)


class SignupView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('Signup', request=UserSignupSerializer)
    def post(self, request):
        data = request.data.copy()
        data = rearrange_tele_input_data(data)
        serializer = UserSignupSerializer(data=data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        validated = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create(
                    first_name=validated['first_name'],
                    last_name=validated['last_name'],
                    phone_country_code=validated.get('phone_country_code'),
                    phone=validated['phone'],
                    email=validated.get('email'),
                    role_type=User.ROLE_USER,
                )
                user.set_password(validated['password'])
                user.save()
                UserProfile.objects.create(
                    user=user,
                    specialization=validated['specialization'],
                    governorate=validated['governorate'],
                    birth_date=validated['birth_date'],
                    profile_completed=True,
                )
                # No code means the student could never verify: keep no half-created account.
                if not OtpService.send(user.phone, client_ip(request)):
                    raise SmsNotSent
        except SmsNotSent:
            return send_error('SMS not sent', {'SmsFailed': ['We could not send the verification code right now. Please try again later.']}, 503)
        except Exception:
            logger.exception('Signup failed (phone=%s)', _mask_phone(validated.get('phone')))
            return send_error('User details not saved', {'UserDetailsNotSaved': ['Could not create the account.']}, 400)
        return send_response('User details saved successfully', {'user': UserResource(user, context={'request': request}).data})


class VerifyOtpView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('VerifyOtp', request=VerifyOtpSerializer)
    def post(self, request):
        user, error = _verify_otp_request(request)
        if error:
            return error

        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])

        user.make_trial_subscription()
        return signed_in_response(request, 'OTP Verification Successfully', user)


class ResendOtpView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ResendOtp')
    def post(self, request):
        phone = _phone_from(request.data)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if not OtpService.can_resend(user.phone):
            return send_error('Too Many Requests', {'otp': ['OTP already sent, please wait a minute']}, 429)

        if not OtpService.send(user.phone, client_ip(request)):
            return send_error('SMS not sent', {'SmsFailed': ['We could not send the verification code right now. Please try again later.']}, 503)
        return send_response('OTP Send Successfully', {
            'phone': user.phone,
            'expires_at': timezone.now() + timezone.timedelta(minutes=OtpService.EXPIRY_MINUTES),
        })


class CheckVerificationView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('CheckVerification')
    def post(self, request):
        # Only reports whether the phone still needs verifying; it never logs anyone in.
        phone = _phone_from(request.data)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        return send_response('success', {
            'user': {'phone': user.phone},
            'go_to_verify': not user.is_phone_verified,
        })


class LoginView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('Login', request=UserLoginSerializer)
    def post(self, request):
        data = request.data.copy()
        data = rearrange_tele_input_data(data)
        serializer = UserLoginSerializer(data=data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        phone = serializer.validated_data['phone']
        password = serializer.validated_data['password']
        ip = client_ip(request)

        if is_throttled(phone, ip):
            return send_error(
                'Too Many Requests',
                {'TooManyAttempts': ['Too many failed attempts. Please try again in 10 minutes.']},
                429,
            )

        user = User.objects.filter(phone=phone).first()
        if not user or not check_password(password, user.password):
            register_failed_attempt(phone, ip)
            _log_failed_login(request, phone)
            return send_error('Unauthorised', {'WrongCredentials': ['Phone number or password is wrong.']}, 422)
        clear_attempts(phone, ip)

        # Block suspended (status != ACTIVE), soft-deleted, or deactivated accounts.
        # Checked only after the password is verified so account state is never
        # revealed to someone who does not know the credentials.
        if not user.is_active_user:
            logger.info(
                'Login blocked: inactive or suspended account (user_id=%s, phone=%s, ip=%s)',
                user.id,
                _mask_phone(phone),
                request.META.get('REMOTE_ADDR'),
                extra={
                    'path': request.path,
                    'method': request.method,
                    'user_id': user.id,
                    'phone': _mask_phone(phone),
                    'ip': request.META.get('REMOTE_ADDR'),
                },
            )
            return send_error(
                'Account Disabled',
                {'AccountDisabled': ['Your account has been suspended. Please contact support.']},
                403,
            )

        if not user.is_phone_verified:
            if OtpService.can_resend(user.phone) and not OtpService.send(user.phone, ip):
                return send_error('SMS not sent', {'SmsFailed': ['We could not send the verification code right now. Please try again later.']}, 503)
            return send_response('OTP Send Successfully', {
                'user': {'phone': user.phone},
                'go_to_verify': True,
            })

        return signed_in_response(request, 'Login Successfully', user)


class ForgetPasswordView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ForgetPassword')
    def post(self, request):
        phone = _phone_from(request.data)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if not OtpService.can_resend(user.phone):
            return send_error('Too Many Requests', {'otp': ['OTP already sent, please wait a minute']}, 429)

        if not OtpService.send(user.phone, client_ip(request)):
            return send_error('SMS not sent', {'SmsFailed': ['We could not send the verification code right now. Please try again later.']}, 503)
        # Only the phone is returned: the caller has not proven they own this account yet.
        return send_response('OTP Send Successfully', {'user': {'phone': user.phone}})


class VerifyOtpForForgetView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('VerifyOtpForForget', request=VerifyOtpSerializer)
    def post(self, request):
        user, error = _verify_otp_request(request)
        if error:
            return error

        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])
        # The reset ticket is the only thing /reset accepts as proof that this OTP step passed.
        return send_response('OTP Verification Successfully', {
            'user': {'phone': user.phone},
            'reset_token': PasswordResetService.issue(user),
        })


class ResetPasswordView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ResetPassword', request=ResetPasswordSerializer)
    def post(self, request):
        serializer = ResetPasswordSerializer(data={**request.data, 'phone': _phone_from(request.data)})
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        user = User.objects.filter(phone=serializer.validated_data['phone']).first()
        if not user or not PasswordResetService.consume(user, serializer.validated_data['reset_token']):
            return send_error(
                'Validation Errors',
                {'reset_token': ['This reset link is invalid or has expired. Please request a new code.']},
                422,
            )

        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])

        return signed_in_response(request, 'Reset Password Done Successfully', user)


class GetUserInfoView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('GetUserInfo')
    def get(self, request):
        return send_response('success', {
            'user': UserResource(request.user, context={'request': request}).data,
        })


class UpdateUserInfoView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('UpdateUserInfo', request=UpdateProfileSerializer)
    def post(self, request):
        serializer = UpdateProfileSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)
        data = serializer.validated_data
        user = request.user
        for field in ['first_name', 'last_name', 'email', 'phone_country_code']:
            if field in data:
                setattr(user, field, data[field])
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field in ['specialization', 'governorate', 'birth_date']:
            if field in data:
                setattr(profile, field, data[field])
        profile.save()

        return send_response('success', {
            'user': UserResource(user, context={'request': request}).data,
        })


class UpdateUserPasswordView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('UpdateUserPassword', request=UpdatePasswordSerializer)
    def post(self, request):
        serializer = UpdatePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        if not check_password(serializer.validated_data['current_password'], request.user.password):
            return send_error('Validation Errors', {'current_password': ['Current password is incorrect.']}, 422)

        request.user.set_password(serializer.validated_data['password'])
        request.user.save()
        return send_response('Password changed successfully', {})


class LogoutView(BaseApiView):
    # Open to everyone so an expired session can still clear its cookies.
    permission_classes = [AllowAny]

    @api_post('Logout')
    def post(self, request):
        return logout_response(send_response('Logout Successfully', {}))
