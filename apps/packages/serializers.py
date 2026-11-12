"""
Package serializers.
"""
from decimal import Decimal
from rest_framework import serializers
from apps.packages.models import Package, UserPackage, DiscountCode


class PackageCategoryResource(serializers.Serializer):
    """The category a package opens, with its parents' names (no subtree: keeps package lists light)."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    level = serializers.IntegerField()
    path = serializers.SerializerMethodField()

    def get_path(self, obj):
        return [c.name for c in obj.get_ancestors(include_self=True)]


class PackageResource(serializers.ModelSerializer):
    category = PackageCategoryResource(read_only=True)
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    original_price = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'code', 'description', 'logo', 'icon', 'price', 'original_price',
            'status', 'period_days', 'duration_minutes', 'number_of_questions',
            'category', 'is_trial', 'is_custom', 'is_bestseller', 'is_new',
            'is_featured', 'daily_rate', 'difficulty_level', 'difficulty_label', 'rating',
            'students_count', 'discount_percentage', 'language',
            'questions_count', 'created_at',
        ]

    def get_questions_count(self, obj):
        """Active questions the package opens (counted once per category for a whole list)."""
        if not obj.category_id:
            return 0
        cache = self.context.setdefault('_questions_by_category', {}) if isinstance(self.context, dict) else {}
        if obj.category_id not in cache:
            from apps.exams.models import Question
            field = {1: 'category_id', 2: 'sub_category_id'}.get(obj.category.level, 'sub_subcategory_id')
            cache[obj.category_id] = Question.objects.filter(
                **{field: obj.category_id}, status=Question.ACTIVE, deleted_at__isnull=True,
            ).count()
        return cache[obj.category_id]

    def get_original_price(self, obj):
        if obj.discount_percentage and obj.discount_percentage > 0 and obj.price is not None:
            factor = Decimal(100) / (Decimal(100) - Decimal(obj.discount_percentage))
            return float(round(Decimal(obj.price) * factor, 2))
        return None


class UserPackageResource(serializers.ModelSerializer):
    package = PackageResource(read_only=True)
    is_active = serializers.SerializerMethodField()
    questions_used = serializers.SerializerMethodField()

    class Meta:
        model = UserPackage
        fields = [
            'id', 'user_id', 'package', 'start_date', 'end_date',
            'price', 'price_before_discount', 'discount', 'pay_id',
            'subscription_status', 'is_active', 'questions_used', 'created_at',
        ]

    def get_is_active(self, obj):
        return bool(obj.is_active)

    def get_questions_used(self, obj):
        """Questions the user has answered since this subscription started."""
        from apps.exams.models import ExamTrialDetail
        answered = ExamTrialDetail.objects.filter(exam_trail__user_id=obj.user_id, answer_id__isnull=False)
        if obj.start_date:
            answered = answered.filter(exam_trail__created_at__date__gte=obj.start_date)
        return answered.count()


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
