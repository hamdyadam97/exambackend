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


class PackagePreviewTests(TestCase):
    def test_preview_shows_real_questions_without_answers(self):
        from apps.exams.models import Answer, Question

        board = Category.objects.create(name='Board')
        uro = Category.objects.create(name='Urology', parent=board, level=2)
        package = Package.objects.create(name='Uro', category=uro, price=40, period_days=30)
        for i in range(5):
            q = Question.objects.create(text_question=f'<p>q{i}</p>', category=board, sub_category=uro, status=1)
            q.correct_answer = Answer.objects.create(question=q, answer_option='<p>right</p>')
            q.save()
            Answer.objects.create(question=q, answer_option='<p>wrong</p>')
        Question.objects.create(text_question='hidden', category=board, sub_category=uro, status=1, needs_review=True)
        data = self.client.get(f'/api/packages/{package.id}/preview').json()['data']
        self.assertEqual(len(data['samples']), 3)
        for s in data['samples']:
            self.assertTrue(s['text'].startswith('<p>q'))
            self.assertEqual(sorted(s['options']), ['<p>right</p>', '<p>wrong</p>'])
            self.assertNotIn('correct', str(s.keys()))
        self.assertEqual(data['package']['questions_count'], 6)


class CouponReasonTests(TestCase):
    def make(self, **kw):
        from datetime import date, timedelta
        today = date.today()
        data = dict(code='INS003', marketer='m', type=DiscountCode.TYPE_PERCENTAGE, percentage=100, quantity=3,
                    from_date=today - timedelta(days=1), to_date=today + timedelta(days=30), status=DiscountCode.STATUS_ACTIVE)
        data.update(kw)
        return DiscountCode.objects.create(**data)

    def test_reasons_and_case_insensitive_code(self):
        from datetime import date, timedelta
        from apps.core.services import CouponService as Core
        c = self.make()
        ok = Core.check_coupon('ins003 ', 45)
        self.assertTrue(ok['valid'])
        self.assertEqual((ok['coupon'], ok['final_price']), ('INS003', 0))
        self.assertEqual(Core.check_coupon('NOPE', 45)['reason'], 'not_found')
        c.used_count = 3; c.save()
        self.assertEqual(Core.check_coupon('INS003', 45)['reason'], 'used_up')
        c.used_count = 0; c.to_date = date.today() - timedelta(days=1); c.save()
        self.assertEqual(Core.check_coupon('INS003', 45)['reason'], 'expired')
        c.to_date = date.today() + timedelta(days=9); c.from_date = date.today() + timedelta(days=2); c.save()
        self.assertEqual(Core.check_coupon('INS003', 45)['reason'], 'not_started')
        c.from_date = date.today(); c.status = DiscountCode.STATUS_INACTIVE; c.save()
        self.assertEqual(Core.check_coupon('INS003', 45)['reason'], 'inactive')

    def test_api_returns_the_reason(self):
        from rest_framework.test import APIClient
        self.make(used_count=8)
        user = User.objects.create_user(phone='+962790000077', password='x' * 10)
        package = Package.objects.create(name='p', price=45, period_days=30, category=Category.objects.create(name='X'))
        client = APIClient()
        client.force_authenticate(user)
        res = client.post('/api/packages/check-coupon', {'coupon': 'INS003', 'package_id': package.id}, format='json')
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()['errors']['reason'], ['used_up'])


class DashboardDateFieldTests(TestCase):
    def test_discount_code_form_has_real_date_pickers(self):
        from django.test import Client
        admin = User.objects.create_superuser(phone='+962790000078', password='admin123', email='d@rootsexams.com')
        client = Client()
        client.force_login(admin)
        html = client.get('/admin/discount_codes/create/').content.decode()
        import re
        tags = re.findall(r'<input[^>]*name="(?:from_date|to_date)"[^>]*>', html)
        self.assertEqual(len(tags), 2, html[:500])
        for tag in tags:
            self.assertRegex(tag, r'type="date"')
            self.assertNotRegex(tag, r'type="text"')
        self.assertNotIn('name="used_count"', html)
