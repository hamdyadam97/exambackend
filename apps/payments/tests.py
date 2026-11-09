"""
Tests for payments app.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import User, UserProfile
from apps.content.models import Category
from apps.packages.models import Package, UserPackage, DiscountCode
from apps.payments.models import Invoice, PaymentTransaction
from apps.payments.services import InvoiceService

GATEWAY = 'apps.payments.services.HyperPayService'


def gateway_payment(code='000.100.110', amount='50.00', currency='JOD', merchant_tx=None):
    return {'id': 'gw-1', 'paymentBrand': 'VISA', 'amount': amount, 'currency': currency,
            'merchantTransactionId': merchant_tx, 'result': {'code': code, 'description': 'test'}}


@override_settings(HYPERPAY_ENTITY_ID='entity', HYPERPAY_AUTHORIZATION='token', PAYMENT_CURRENCY='JOD')
class HyperPayFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='+962790000009', password='x' * 10)
        UserProfile.objects.create(user=self.user, profile_completed=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.package = Package.objects.create(
            name='Paid', category=Category.objects.create(name='C'), price=Decimal('50.00'), period_days=30,
        )

    def subscribe(self, **extra):
        with patch(f'{GATEWAY}.create_checkout', return_value='checkout-123') as create:
            res = self.client.post('/api/packages/subscribe', {'package_id': self.package.id, **extra}, format='json')
        return res, create

    def confirm(self, payment_id, payment):
        with patch(f'{GATEWAY}.get_payment', return_value=payment):
            return self.client.post('/api/payment/confirm', {'payment_id': payment_id}, format='json')

    def test_subscribe_opens_a_checkout_without_granting(self):
        res, create = self.subscribe()
        self.assertEqual(res.status_code, 200)
        payment_id = res.json()['data']['checkout']['payment_id']
        create.assert_called_once_with(Decimal('50.00'), 'JOD', payment_id)
        self.assertFalse(UserPackage.objects.filter(user=self.user).exists())

        info = self.client.get(f'/api/payment/info?id={payment_id}').json()['data']
        self.assertIn('checkoutId=checkout-123', info['widget_url'])

    def test_unpaid_checkout_is_not_granted(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        res = self.confirm(payment_id, gateway_payment(code='800.100.151', merchant_tx=payment_id))
        self.assertEqual(res.status_code, 402)
        self.assertFalse(UserPackage.objects.filter(user=self.user).exists())

    def test_paid_checkout_is_granted_once(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        for _ in range(2):  # The result page may confirm more than once.
            res = self.confirm(payment_id, gateway_payment(merchant_tx=payment_id))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()['data']['status'], 'paid')
        self.assertEqual(UserPackage.objects.filter(user=self.user).count(), 1)
        self.assertTrue(PaymentTransaction.objects.get(payment_id=payment_id).is_success)

    def test_payment_for_a_different_amount_is_rejected(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        res = self.confirm(payment_id, gateway_payment(amount='1.00', merchant_tx=payment_id))
        self.assertEqual(res.status_code, 402)
        self.assertFalse(UserPackage.objects.exists())

    def test_payment_from_another_transaction_is_rejected(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        res = self.confirm(payment_id, gateway_payment(merchant_tx='someone-elses-payment'))
        self.assertEqual(res.status_code, 402)

    def test_cannot_confirm_another_users_payment(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        other = User.objects.create_user(phone='+962790000010', password='y' * 10)
        self.client.force_authenticate(other)
        self.assertEqual(self.confirm(payment_id, gateway_payment(merchant_tx=payment_id)).status_code, 404)

    def test_pending_payment_waits(self):
        payment_id = self.subscribe()[0].json()['data']['checkout']['payment_id']
        res = self.confirm(payment_id, gateway_payment(code='000.200.000', merchant_tx=payment_id))
        self.assertEqual(res.json()['data']['status'], 'pending')
        self.assertFalse(UserPackage.objects.exists())

    def test_coupon_use_is_counted_when_paid(self):
        from django.utils import timezone
        today = timezone.now().date()
        DiscountCode.objects.create(
            code='HALF', marketer='m', type=DiscountCode.TYPE_PERCENTAGE, percentage=50, quantity=10,
            from_date=today, to_date=today, status=DiscountCode.STATUS_ACTIVE,
        )
        res, create = self.subscribe(coupon='HALF')
        payment_id = res.json()['data']['checkout']['payment_id']
        self.assertEqual(create.call_args[0][0], Decimal('25.00'))
        self.confirm(payment_id, gateway_payment(amount='25.00', merchant_tx=payment_id))
        self.assertEqual(DiscountCode.objects.get(code='HALF').used_count, 1)

    @override_settings(HYPERPAY_ENTITY_ID='', HYPERPAY_AUTHORIZATION='')
    def test_paid_package_refused_when_gateway_not_configured(self):
        res = self.client.post('/api/packages/subscribe', {'package_id': self.package.id}, format='json')
        self.assertEqual(res.status_code, 503)
        self.assertFalse(UserPackage.objects.exists())


class InvoiceServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.category = Category.objects.create(name='Test Category')
        self.package = Package.objects.create(
            name='Test Package',
            price=Decimal('50.00'),
            category=self.category,
        )
        self.subscription = UserPackage.objects.create(
            user=self.user,
            package=self.package,
            price=Decimal('50.00'),
        )

    def test_create_invoice(self):
        invoice = InvoiceService.create_invoice(self.subscription)
        self.assertEqual(invoice.user, self.user)
        self.assertEqual(invoice.total_amount, Decimal('50.00'))
        self.assertEqual(invoice.status, Invoice.STATUS_DRAFT)

    def test_mark_sent(self):
        invoice = InvoiceService.create_invoice(self.subscription)
        InvoiceService.mark_sent(invoice, self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_SENT)
        self.assertTrue(invoice.sent_to_accounting)
