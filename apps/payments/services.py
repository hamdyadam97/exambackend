"""
Payment domain services.
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

from apps.payments.models import PaymentTransaction, MoneyLog, Invoice
from apps.users.services import AuditService

logger = logging.getLogger('api')


class HyperPayService:
    """HyperPay payment gateway integration."""

    @staticmethod
    def create_checkout(amount, currency='JOD', payment_type='visa'):
        if not settings.HYPERPAY_ENTITY_ID:
            return {'checkout_id': None, 'url': None, 'error': 'HyperPay not configured'}
        # Placeholder for HyperPay integration.
        return {'checkout_id': None, 'url': None}

    @staticmethod
    def get_payment_status(resource_path):
        if not settings.HYPERPAY_ENTITY_ID:
            return {}
        url = f"{settings.HYPERPAY_BASE_URL}{resource_path}"
        headers = {'Authorization': f"Bearer {settings.HYPERPAY_AUTHORIZATION}"}
        try:
            response = requests.get(url, headers=headers, params={'entityId': settings.HYPERPAY_ENTITY_ID}, timeout=30)
            return response.json()
        except Exception as e:
            logger.error('HyperPay status check failed', extra={'error': str(e)})
            return {}

    @classmethod
    def record_transaction(cls, user, package, data):
        transaction = PaymentTransaction.objects.create(
            user=user,
            package=package,
            transaction_type=data.get('type', 'payment'),
            payment_id=data.get('payment_id', ''),
            payment_brand=data.get('payment_brand', ''),
            gateway_transaction_id=data.get('transaction_id', ''),
            amount=Decimal(data.get('amount', 0)),
            currency=data.get('currency', 'USD'),
            result_summary=data.get('result', {}),
            is_success=data.get('is_success', False),
            coupon_code=data.get('coupon'),
        )
        AuditService.log(
            action='payment_recorded',
            entity_type='PaymentTransaction',
            entity_id=transaction.id,
            user=user,
            metadata={'amount': str(transaction.amount), 'payment_id': transaction.payment_id},
        )
        return transaction


class InvoiceService:
    """Invoice lifecycle management."""

    @classmethod
    def create_invoice(cls, user_package, created_by=None):
        invoice = Invoice.objects.create(
            user=user_package.user,
            user_package=user_package,
            invoice_number=f"INV-{user_package.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=user_package.price,
            created_by=created_by,
        )
        AuditService.log(
            action='invoice_created',
            entity_type='Invoice',
            entity_id=invoice.id,
            user=user_package.user,
            metadata={'amount': str(invoice.total_amount)},
        )
        return invoice

    @classmethod
    def mark_sent(cls, invoice, sent_by):
        invoice.status = Invoice.STATUS_SENT
        invoice.sent_to_accounting = True
        invoice.sent_at = timezone.now()
        invoice.sent_by = sent_by
        invoice.save()
        return invoice
