"""
Package API views.
"""
import uuid
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q
from apps.packages.models import Package, UserPackage, DiscountCode
from apps.packages.serializers import (
    PackageResource, UserPackageResource, CheckCouponSerializer, SubscribeSerializer,
)
from apps.payments.models import PaymentTransaction
from apps.content.models import Category, Instructor, Faq, Testimonial
from apps.content.serializers import CategoryResource, InstructorResource, FaqResource, TestimonialResource
from apps.core.utils import api_response, send_response, send_error, api_get, api_post
from apps.core.services import CouponService, HyperPayService
from django.utils import timezone


class BaseApiView(APIView):
    pass


class PackageDataView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('PackageData')
    def get(self, request):
        categories = list(Package.objects.filter(status=1).exclude(category__isnull=True).values_list('category_id', flat=True).distinct())
        sub_categories = Category.objects.filter(status=1, level=Category.LEVEL_SUB_CATEGORY).annotate(
            packages_count=Count('packages', filter=Q(packages__status=1))
        ).order_by('name')
        return api_response(True, 'Fetched Successfully', {
            'categories': categories,
            'sub_categories': CategoryResource(sub_categories, many=True, context={'request': request}).data,
        })


class PackageListView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('PackageList')
    def get(self, request):
        packages = Package.objects.filter(status=1, is_trial=False).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'packages': PackageResource(packages, many=True, context={'request': request}).data,
        })


class PackageDetailView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('PackageDetail')
    def get(self, request, pk):
        try:
            package = Package.objects.get(pk=pk, status=1)
        except Package.DoesNotExist:
            return send_error('Package not found', {}, 404)
        return api_response(True, 'Fetched Successfully', {
            'package': PackageResource(package, context={'request': request}).data,
        })


class RelatedPackagesView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('RelatedPackages')
    def get(self, request, pk):
        try:
            package = Package.objects.get(pk=pk, status=1)
        except Package.DoesNotExist:
            return send_error('Package not found', {}, 404)
        related = Package.objects.filter(status=1, category=package.category).exclude(pk=pk)[:5]
        return api_response(True, 'Fetched Successfully', {
            'packages': PackageResource(related, many=True, context={'request': request}).data,
        })


class SubCategoryPackagesView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('SubCategoryPackages')
    def get(self, request, pk):
        try:
            sub = Category.objects.get(pk=pk, level=Category.LEVEL_SUB_CATEGORY)
        except Category.DoesNotExist:
            return send_error('Subcategory not found', {}, 404)

        # Packages attach to the specialty (root) or directly to the
        # sub-category; both belong to this sub-category's catalog.
        category_ids = [sub.id]
        if sub.parent_id:
            category_ids.append(sub.parent_id)

        packages = Package.objects.filter(
            status=Package.ACTIVE,
            is_trial=False,
            deleted_at__isnull=True,
            category_id__in=category_ids,
        ).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'packages': PackageResource(packages, many=True, context={'request': request}).data,
        })


class CoursesView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Courses')
    def get(self, request):
        packages = Package.objects.filter(status=Package.ACTIVE, is_trial=False, deleted_at__isnull=True)
        featured = packages.filter(is_featured=True).order_by('-created_at')[:6]
        all_courses = packages.order_by('-created_at')
        categories = Category.objects.filter(status=Category.ACTIVE, level=Category.LEVEL_CATEGORY).annotate(
            courses_count=Count('packages', filter=Q(packages__status=Package.ACTIVE, packages__deleted_at__isnull=True))
        ).order_by('name')
        instructors = Instructor.objects.filter(status=Instructor.ACTIVE).order_by('-created_at')
        faqs = Faq.objects.filter(status=Faq.ACTIVE).order_by('order', '-created_at')[:10]
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')[:10]

        from django.db.models import Sum
        stats = packages.aggregate(
            total_students=Sum('students_count'),
            total_courses=Count('id'),
        )
        instructor_stats = Instructor.objects.filter(status=Instructor.ACTIVE).aggregate(
            total_instructors=Count('id'),
            certificates=Sum('certificates_count'),
        )

        return api_response(True, 'Fetched Successfully', {
            'featured': PackageResource(featured, many=True, context={'request': request}).data,
            'courses': PackageResource(all_courses, many=True, context={'request': request}).data,
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
            'instructors': InstructorResource(instructors, many=True, context={'request': request}).data,
            'faqs': FaqResource(faqs, many=True).data,
            'testimonials': TestimonialResource(testimonials, many=True).data,
            'stats': {
                'total_courses': stats['total_courses'] or 0,
                'total_students': stats['total_students'] or 0,
                'total_instructors': instructor_stats['total_instructors'] or 0,
                'certificates_issued': instructor_stats['certificates'] or 0,
            },
        })


class UserSubscriptionView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('UserSubscription')
    def get(self, request):
        subs = UserPackage.objects.filter(user=request.user).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'subscriptions': UserPackageResource(subs, many=True, context={'request': request}).data,
        })


class CheckCouponView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('CheckCoupon', request=CheckCouponSerializer)
    def post(self, request):
        serializer = CheckCouponSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)
        try:
            package = Package.objects.get(pk=serializer.validated_data['package_id'])
        except Package.DoesNotExist:
            return send_error('Package not found', {}, 404)
        result = CouponService.check_coupon(serializer.validated_data['coupon'], package.price)
        if not result['valid']:
            return send_error('Invalid Coupon', {'coupon': [result['message']]}, 422)
        return api_response(True, 'Coupon applied', result)


class PackageCalculatePriceView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('PackageCalculatePrice')
    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        try:
            package = Package.objects.get(pk=serializer.validated_data['package_id'])
        except Package.DoesNotExist:
            return send_error('Package not found', {}, 404)

        custom_days = serializer.validated_data.get('custom_days')
        if package.is_custom:
            if not custom_days:
                return send_error('Validation Errors', {'custom_days': ['Please select number of days.']}, 422)
            if not package.daily_rate:
                return send_error('Configuration error', {'daily_rate': ['Daily rate not set.']}, 500)
            price = float(package.daily_rate) * custom_days
            period_days = custom_days
        else:
            price = float(package.price or 0)
            period_days = int(package.period_days or 0)

        return api_response(True, 'Price calculated', {
            'price': price,
            'period_days': period_days,
            'is_custom': package.is_custom,
        })


class SubscribeView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('Subscribe', request=SubscribeSerializer)
    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        try:
            package = Package.objects.get(pk=serializer.validated_data['package_id'])
        except Package.DoesNotExist:
            return send_error('Package not found', {}, 404)

        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.profile_completed:
            return send_error('Profile incomplete', {'profile': ['Please complete your profile before subscribing.']}, 422)

        custom_days = serializer.validated_data.get('custom_days')
        if package.is_custom:
            if not custom_days:
                return send_error('Validation Errors', {'custom_days': ['Please select number of days for custom package.']}, 422)
            if not package.daily_rate:
                return send_error('Configuration error', {'daily_rate': ['Custom package daily rate not set.']}, 500)
            price = float(package.daily_rate) * custom_days
            period_days = custom_days
        else:
            price = float(package.price or 0)
            period_days = int(package.period_days or 0)

        coupon_code = serializer.validated_data.get('coupon')
        if coupon_code:
            coupon_result = CouponService.check_coupon(coupon_code, price)
            if coupon_result['valid']:
                price = coupon_result['final_price']

        if price == 0:
            sub = UserPackage.objects.create(
                user=request.user,
                package=package,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timezone.timedelta(days=period_days),
                price=0,
            )
            return api_response(True, 'Subscribed successfully', {
                'subscription': UserPackageResource(sub, context={'request': request}).data,
            })

        checkout = HyperPayService.create_checkout(price)
        if not checkout.get('checkout_id'):
            # Gateway not configured: create a pending transaction the user
            # completes through the built-in checkout page (simulation flow).
            tx = PaymentTransaction.objects.create(
                user=request.user,
                package=package,
                transaction_type='checkout',
                payment_id=uuid.uuid4().hex[:20],
                amount=price,
                currency='JOD',
                result_summary={
                    'custom_days': custom_days,
                    'coupon': coupon_code,
                    'period_days': period_days,
                },
            )
            checkout = {'checkout_id': tx.payment_id, 'url': f'/payment/checkout?id={tx.payment_id}'}

        return api_response(True, 'Redirect to payment', {
            'checkout': checkout,
            'amount': price,
            'period_days': period_days,
        })


class StoreSubscribeView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('StoreSubscribe')
    def post(self, request):
        # Placeholder for payment callback handling
        return api_response(True, 'Subscription stored', {})
