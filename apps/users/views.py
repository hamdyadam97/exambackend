"""
User API views.
"""
import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from apps.users.models import User, UserProfile
from apps.users.serializers import (
    UserResource, UserLoginSerializer, UserSignupSerializer,
    VerifyOtpSerializer, ForgetPasswordSerializer, ResetPasswordSerializer,
    UpdateProfileSerializer, UpdatePasswordSerializer,
)
from apps.core.utils import api_response, send_response, send_error, api_get, api_post, rearrange_tele_input_data, generate_otp
from apps.core.services import SmsService

logger = logging.getLogger('api')


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


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'token': str(refresh.access_token),
        'token_expired_at': timezone.now() + refresh.access_token.lifetime,
        'refresh': str(refresh),
    }


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
                otp = generate_otp()
                user = User.objects.create(
                    first_name=validated['first_name'],
                    last_name=validated['last_name'],
                    phone_country_code=validated.get('phone_country_code'),
                    phone=validated['phone'],
                    email=validated.get('email'),
                    role_type=User.ROLE_USER,
                    otp=otp,
                    otp_expires_at=timezone.now() + timezone.timedelta(minutes=20),
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
                SmsService.send_otp(user.phone, otp)
                return send_response('User details saved successfully', {'user': UserResource(user, context={'request': request}).data})
        except Exception as e:
            return send_error('User details not saved', {'UserDetailsNotSaved': [str(e)]}, 400)


class VerifyOtpView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('VerifyOtp', request=VerifyOtpSerializer)
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        try:
            user = User.objects.get(phone=serializer.validated_data['phone'])
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if not user.otp_expires_at or user.otp_expires_at < timezone.now():
            return send_error('Validation Errors', {'otp': ['OTP expired']}, 422)

        if user.otp != serializer.validated_data['otp']:
            return send_error('Validation Errors', {'otp': ['Invalid OTP']}, 422)

        user.is_phone_verified = True
        user.otp = None
        user.otp_expires_at = None
        user.save()

        user.make_trial_subscription()
        tokens = get_tokens_for_user(user)
        return send_response('OTP Verification Successfully', {
            **tokens,
            'user': UserResource(user, context={'request': request}).data,
        })


class ResendOtpView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ResendOtp')
    def post(self, request):
        phone = request.data.get('phone')
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if user.otp_expires_at and user.otp_expires_at > timezone.now():
            return send_error('Too Many Requests', {'otp': ['OTP already sent, please wait']}, 429)

        otp = generate_otp()
        user.otp = otp
        user.otp_expires_at = timezone.now() + timezone.timedelta(minutes=20)
        user.save()
        SmsService.send_otp(user.phone, otp)
        return send_response('OTP Send Successfully', {
            'phone': user.phone,
            'expires_at': user.otp_expires_at,
        })


class CheckVerificationView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('CheckVerification')
    def post(self, request):
        phone = request.data.get('phone')
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if user.is_phone_verified:
            user.make_trial_subscription()
            tokens = get_tokens_for_user(user)
            return send_response('success', {
                **tokens,
                'user': UserResource(user, context={'request': request}).data,
            })
        return send_response('success', {
            'user': {'phone': user.phone},
            'go_to_verify': True,
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

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            _log_failed_login(request, phone)
            return send_error('Unauthorised', {'WrongCredentials': ['Phone number or password is wrong.']}, 422)

        if not check_password(password, user.password):
            _log_failed_login(request, phone)
            return send_error('Unauthorised', {'WrongCredentials': ['Phone number or password is wrong.']}, 422)

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
            otp = generate_otp()
            user.otp = otp
            user.otp_expires_at = timezone.now() + timezone.timedelta(minutes=20)
            user.save()
            SmsService.send_otp(user.phone, otp)
            return send_response('OTP Send Successfully', {
                'user': {'phone': user.phone},
                'go_to_verify': True,
            })

        tokens = get_tokens_for_user(user)
        return send_response('Login Successfully', {
            **tokens,
            'user': UserResource(user, context={'request': request}).data,
        })


class ForgetPasswordView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ForgetPassword')
    def post(self, request):
        data = request.data.copy()
        data = rearrange_tele_input_data(data)
        phone = data.get('phone')
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        otp = generate_otp()
        user.otp = otp
        user.otp_expires_at = timezone.now() + timezone.timedelta(minutes=20)
        user.save()
        SmsService.send_otp(user.phone, otp)
        return send_response('OTP Send Successfully', {
            'user': UserResource(user, context={'request': request}).data,
        })


class VerifyOtpForForgetView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('VerifyOtpForForget', request=VerifyOtpSerializer)
    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        try:
            user = User.objects.get(phone=serializer.validated_data['phone'])
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        if not user.otp_expires_at or user.otp_expires_at < timezone.now():
            return send_error('Validation Errors', {'otp': ['OTP expired']}, 422)

        if user.otp != serializer.validated_data['otp']:
            return send_error('Validation Errors', {'otp': ['Invalid OTP']}, 422)

        user.otp = None
        user.otp_expires_at = None
        user.is_phone_verified = True
        user.save()
        return send_response('OTP Verification Successfully', {
            'user': UserResource(user, context={'request': request}).data,
        })


class ResetPasswordView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('ResetPassword', request=ResetPasswordSerializer)
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        try:
            user = User.objects.get(phone=serializer.validated_data['phone'])
        except User.DoesNotExist:
            return send_error('Validation Errors', {'phone': ['Invalid phone number.']}, 422)

        user.set_password(serializer.validated_data['password'])
        user.is_phone_verified = True
        user.otp = None
        user.otp_expires_at = None
        user.save()

        tokens = get_tokens_for_user(user)
        return send_response('Reset Password Done Successfully', {
            **tokens,
            'user': UserResource(user, context={'request': request}).data,
        })


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
    permission_classes = [IsAuthenticated]

    @api_post('Logout')
    def post(self, request):
        return send_response('Logout Successfully', {})
