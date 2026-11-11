"""
User serializers.
"""
import re

from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from apps.users.models import User, UserProfile
from apps.content.serializers import CategoryResource

# +962 then a mobile prefix 77/78/79 and 7 digits: the only numbers the SMS gateway delivers to.
JORDAN_MOBILE = re.compile(r'^\+9627[789]\d{7}$')


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['specialization', 'governorate', 'birth_date', 'profile_completed']


class UserResource(serializers.ModelSerializer):
    name_short = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    active_subscriptions_count = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    sub_categories = serializers.SerializerMethodField()
    sub_sub_categories = serializers.SerializerMethodField()
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'name_short', 'first_name', 'last_name', 'email',
            'phone_country_code', 'phone',
            'image', 'active_subscriptions_count', 'categories', 'sub_categories',
            'sub_sub_categories', 'profile',
            'role_type', 'status',
        ]

    def get_name_short(self, obj):
        first = (obj.first_name or '')[:1]
        last = (obj.last_name or '')[:1]
        return f"{first}.{last}".upper()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.thumb and request:
            return request.build_absolute_uri(f'/storage/user_image/{obj.thumb}')
        return None

    def get_active_subscriptions_count(self, obj):
        return obj.active_subscriptions().count()

    def get_categories(self, obj):
        qs = obj.subscribed_categories()
        return CategoryResource(qs, many=True, context=self.context).data

    def get_sub_categories(self, obj):
        qs = obj.subscribed_sub_categories()
        return CategoryResource(qs, many=True, context=self.context).data

    def get_sub_sub_categories(self, obj):
        qs = obj.subscribed_sub_sub_categories()
        return CategoryResource(qs, many=True, context=self.context).data


class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField()


class UserSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    phone_country_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    password = serializers.CharField(min_length=8)
    password_confirmation = serializers.CharField(min_length=8)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    specialization = serializers.CharField(max_length=255)
    governorate = serializers.CharField(max_length=255)
    birth_date = serializers.DateField()

    def validate_email(self, value):
        # Optional: an empty field means no email. Stored as NULL because the column is unique.
        if not value:
            return None
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value

    def validate(self, data):
        if data.get('password') != data.get('password_confirmation'):
            raise serializers.ValidationError({'password': ['Password confirmation does not match.']})
        # Verification codes are delivered by a Jordanian SMS gateway, so only Jordanian mobiles can sign up.
        if not JORDAN_MOBILE.match(data.get('phone') or ''):
            raise serializers.ValidationError({'PhoneNotJordanian': ['Registration is available for Jordanian mobile numbers only (+962 7X XXX XXXX).']})
        if User.objects.filter(phone=data.get('phone')).exists():
            raise serializers.ValidationError({'PhoneTaken': ['This phone number is already registered. Please log in.']})
        return data


class VerifyOtpSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp = serializers.CharField(max_length=6, min_length=6)


class ForgetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()
    # Issued by /forget-verify-otp; proves the OTP step was passed for this phone.
    reset_token = serializers.CharField()
    password = serializers.CharField(min_length=8)
    password_confirmation = serializers.CharField(min_length=8)

    def validate(self, data):
        if data.get('password') != data.get('password_confirmation'):
            raise serializers.ValidationError({'password': ['Password confirmation does not match.']})
        return data


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    email = serializers.EmailField(required=False, allow_null=True)
    phone_country_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    specialization = serializers.CharField(max_length=255, required=False)
    governorate = serializers.CharField(max_length=255, required=False)
    birth_date = serializers.DateField(required=False)


class UpdatePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    password = serializers.CharField(min_length=8)
    password_confirmation = serializers.CharField(min_length=8)

    def validate(self, data):
        if data.get('password') != data.get('password_confirmation'):
            raise serializers.ValidationError({'password': ['Password confirmation does not match.']})
        return data
