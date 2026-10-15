"""
Package serializers.
"""
from decimal import Decimal
from rest_framework import serializers
from apps.packages.models import Package, UserPackage, DiscountCode
from apps.content.serializers import CategoryResource, InstructorResource


class PackageResource(serializers.ModelSerializer):
    category = CategoryResource(read_only=True)
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    original_price = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'code', 'description', 'logo', 'icon', 'price', 'original_price',
            'status', 'period_days', 'duration_minutes', 'number_of_questions',
            'category', 'instructor', 'is_trial', 'is_custom', 'is_bestseller', 'is_new',
            'is_featured', 'daily_rate', 'difficulty_level', 'difficulty_label', 'rating',
            'students_count', 'discount_percentage', 'language', 'lessons_count',
            'created_at',
        ]

    def get_original_price(self, obj):
        if obj.discount_percentage and obj.discount_percentage > 0 and obj.price is not None:
            factor = Decimal(100) / (Decimal(100) - Decimal(obj.discount_percentage))
            return float(round(Decimal(obj.price) * factor, 2))
        return None


class UserPackageResource(serializers.ModelSerializer):
    package = PackageResource(read_only=True)

    class Meta:
        model = UserPackage
        fields = [
            'id', 'user_id', 'package', 'start_date', 'end_date',
            'price', 'price_before_discount', 'discount', 'pay_id',
            'subscription_status', 'created_at',
        ]


class DiscountCodeResource(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = '__all__'


class CheckCouponSerializer(serializers.Serializer):
    coupon = serializers.CharField()
    package_id = serializers.IntegerField()


class SubscribeSerializer(serializers.Serializer):
    package_id = serializers.IntegerField()
    coupon = serializers.CharField(required=False, allow_blank=True)
    custom_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    payment_type = serializers.CharField(default='visa')
