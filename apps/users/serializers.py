"""
User serializers.
"""
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from apps.users.models import User, UserProfile
from apps.content.serializers import CategoryResource


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
    email = serializers.EmailField(required=False, allow_null=True)
    specialization = serializers.CharField(max_length=255)
    governorate = serializers.CharField(max_length=255)
    birth_date = serializers.DateField()

    def validate(self, data):
        if data.get('password') != data.get('password_confirmation'):
            raise serializers.ValidationError({'password': ['Password confirmation does not match.']})
        return data


class VerifyOtpSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp = serializers.CharField(max_length=6, min_length=6)


class ForgetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()
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
