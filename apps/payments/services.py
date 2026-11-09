"""
Payment domain services.
"""
import logging
import re
import requests
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.payments.models import PaymentTransaction, MoneyLog, Invoice
from apps.users.services import AuditService

logger = logging.getLogger('api')


class HyperPayError(Exception):
    """The gateway could not be reached or refused the request."""


class HyperPayService:
    """
    HyperPay COPYandPAY: the server opens a checkout, the shopper pays in HyperPay's own widget,
    and the server then asks HyperPay for the result. Card data never touches this server.
    https://hyperpay.docs.oppwa.com/integrations/widget
    """

    # Result-code groups from the HyperPay docs.
    SUCCESS = re.compile(r'^(000\.000\.|000\.100\.1|000\.[36])')
    PENDING = re.compile(r'^(000\.200|800\.400\.5|100\.400\.500)')
    CHECKOUT_CREATED = re.compile(r'^000\.200\.100')
    TIMEOUT_SECONDS = 30

    @staticmethod
    def is_configured():
        return bool(settings.HYPERPAY_ENTITY_ID and settings.HYPERPAY_AUTHORIZATION)

    @staticmethod
    def _headers():
        token = settings.HYPERPAY_AUTHORIZATION.strip()
        if not token.lower().startswith('bearer '):
            token = f'Bearer {token}'
        return {'Authorization': token}

    @classmethod
    def widget_url(cls, checkout_id):
        return f'{settings.HYPERPAY_BASE_URL}/v1/paymentWidgets.js?checkoutId={checkout_id}'

    @classmethod
    def create_checkout(cls, amount: Decimal, currency: str, merchant_transaction_id: str) -> str:
        """Open a checkout for the amount and return its id."""
        try:
            response = requests.post(
                f'{settings.HYPERPAY_BASE_URL}/v1/checkouts',
                headers=cls._headers(),
                data={
                    'entityId': settings.HYPERPAY_ENTITY_ID,
                    'amount': f'{Decimal(amount):.2f}',
                    'currency': currency,
                    'paymentType': 'DB',
                    'merchantTransactionId': merchant_transaction_id,
                },
                timeout=cls.TIMEOUT_SECONDS,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error('HyperPay checkout failed: %s', e)
            raise HyperPayError('Payment gateway unavailable') from e

        code = data.get('result', {}).get('code', '')
        if not cls.CHECKOUT_CREATED.match(code) or not data.get('id'):
            logger.error('HyperPay refused checkout: %s %s', code, data.get('result', {}).get('description'))
            raise HyperPayError('Payment gateway refused the checkout')
        return data['id']

    @classmethod
    def get_payment(cls, checkout_id: str) -> dict:
        """The gateway's record of the payment made in a checkout."""
        try:
            response = requests.get(
                f'{settings.HYPERPAY_BASE_URL}/v1/checkouts/{checkout_id}/payment',
                headers=cls._headers(),
                params={'entityId': settings.HYPERPAY_ENTITY_ID},
                timeout=cls.TIMEOUT_SECONDS,
            )
            return response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error('HyperPay status check failed: %s', e)
            raise HyperPayError('Payment gateway unavailable') from e


class PaymentService:
    """Turns a verified gateway payment into a subscription, exactly once."""

    STATUS_PAID, STATUS_PENDING, STATUS_FAILED = 'paid', 'pending', 'failed'

    @classmethod
    def verify_and_grant(cls, tx: PaymentTransaction):
        """
        Ask HyperPay about the transaction's checkout and grant the subscription when it was paid.
        Returns (status, subscription_or_None). Safe to call repeatedly and concurrently.
        """
        from apps.packages.models import UserPackage, DiscountCode
        from django.db.models import F

        if tx.is_success:
            return cls.STATUS_PAID, UserPackage.objects.filter(pay_id=tx.id).first()

        checkout_id = (tx.result_summary or {}).get('checkout_id')
        if not checkout_id:
            return cls.STATUS_FAILED, None
        payment = HyperPayService.get_payment(checkout_id)
        code = payment.get('result', {}).get('code', '')

        if HyperPayService.PENDING.match(code):
            return cls.STATUS_PENDING, None
        if not HyperPayService.SUCCESS.match(code):
            cls._remember(tx, code, payment)
            return cls.STATUS_FAILED, None

        # Paid according to HyperPay: it must also be for this transaction and this exact amount.
        paid_amount = Decimal(str(payment.get('amount') or '0'))
        if (
            payment.get('merchantTransactionId') != tx.payment_id
            or paid_amount != Decimal(tx.amount)
            or payment.get('currency') != tx.currency
        ):
            logger.error('HyperPay payment does not match transaction %s', tx.payment_id)
            cls._remember(tx, 'mismatch', payment)
            return cls.STATUS_FAILED, None

        with transaction.atomic():
            locked = PaymentTransaction.objects.select_for_update().get(pk=tx.pk)
            if locked.is_success:  # Another request granted it first.
                return cls.STATUS_PAID, UserPackage.objects.filter(pay_id=locked.id).first()

            info = locked.result_summary or {}
            period_days = int(info.get('period_days') or (locked.package.period_days if locked.package else 0) or 0)
            subscription = UserPackage.objects.create(
                user=locked.user,
                package=locked.package,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timezone.timedelta(days=period_days),
                price=locked.amount,
                pay_id=locked.id,  # Links the subscription to the payment that bought it.
            )
            locked.is_success = True
            locked.gateway_transaction_id = payment.get('id')
            locked.payment_brand = payment.get('paymentBrand')
            locked.result_summary = {**info, 'code': code, 'paid_at': timezone.now().isoformat()}
            locked.save(update_fields=['is_success', 'gateway_transaction_id', 'payment_brand', 'result_summary', 'updated_at'])

            if locked.coupon_code:
                DiscountCode.objects.filter(code=locked.coupon_code).update(used_count=F('used_count') + 1)
            MoneyLog.objects.create(
                user=locked.user,
                platform=MoneyLog.PLATFORM_WEB,
                item=locked.package,
                payment_id=locked.payment_id,
                status=1,
                coupon_code=locked.coupon_code,
            )
            AuditService.log(
                action='payment_verified',
                entity_type='PaymentTransaction',
                entity_id=locked.id,
                user=locked.user,
                metadata={'amount': str(locked.amount), 'code': code},
            )
        return cls.STATUS_PAID, subscription

    @staticmethod
    def _remember(tx, code, payment):
        """Keep the gateway's answer for support, without card details."""
        tx.result_summary = {
            **(tx.result_summary or {}),
            'code': code,
            'description': payment.get('result', {}).get('description'),
        }
        tx.save(update_fields=['result_summary', 'updated_at'])

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
