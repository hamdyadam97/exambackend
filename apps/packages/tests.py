"""
Tests for packages app.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.users.models import User
from apps.content.models import Category
from apps.packages.models import Package, DiscountCode
from apps.packages.services import CouponService, SubscriptionService


class CouponServiceTests(TestCase):
    def setUp(self):
        self.coupon = DiscountCode.objects.create(
            code='SAVE10',
            marketer='Test',
            type=DiscountCode.TYPE_PERCENTAGE,
            percentage=10,
            quantity=10,
            from_date=timezone.now().date() - timezone.timedelta(days=1),
            to_date=timezone.now().date() + timezone.timedelta(days=1),
            status=DiscountCode.STATUS_ACTIVE,
        )

    def test_valid_percentage_coupon(self):
        result = CouponService.check_coupon('SAVE10', 100)
        self.assertTrue(result['valid'])
        self.assertEqual(result['final_price'], 90)

    def test_invalid_coupon(self):
        result = CouponService.check_coupon('INVALID', 100)
        self.assertFalse(result['valid'])


class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.category = Category.objects.create(name='Test Category')
        self.package = Package.objects.create(
            name='Test Package',
            price=Decimal('50.00'),
            period_days=30,
            category=self.category,
        )

    def test_subscribe(self):
        sub = SubscriptionService.subscribe(self.user, self.package)
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.price, Decimal('50.00'))
        self.assertIsNotNone(sub.end_date)
