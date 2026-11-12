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


class ImportPackagesTests(TestCase):
    def test_import_links_the_right_category_and_is_rerunnable(self):
        import json
        import tempfile
        from django.core.management import call_command

        call_command('seed_taxonomy', verbosity=0)
        rows = [
            {'name': 'Urology Board - 1 Month', 'price': 40, 'period_days': 30,
             'path': ['Residency and Board Exams', 'Urology'], 'active': True},
            {'name': 'Free Trial - 7 يوم', 'price': 0, 'period_days': 7, 'path': ['Free Trial (20 questions)'],
             'active': True, 'is_trial': True, 'number_of_questions': 20},
        ]
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(rows, f)
        f.close()
        call_command('import_packages', f.name, verbosity=0)
        call_command('import_packages', f.name, verbosity=0)
        self.assertEqual(Package.objects.count(), 2)
        urology = Package.objects.get(name='Urology Board - 1 Month')
        self.assertEqual((urology.category.name, urology.category.parent.name), ('Urology', 'Residency and Board Exams'))
        trial = Package.objects.get(is_trial=True)
        self.assertEqual((trial.category.name, trial.period_days, trial.number_of_questions), ('Free Trial (20 questions)', 7, 20))
