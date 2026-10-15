"""
Tests for payments app.
"""
from decimal import Decimal
from django.test import TestCase
from apps.users.models import User
from apps.content.models import Category
from apps.packages.models import Package, UserPackage
from apps.payments.models import Invoice
from apps.payments.services import InvoiceService


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
