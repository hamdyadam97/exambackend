"""
Payment API views.
"""
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.core.utils import api_response, send_error, api_get, api_post
from apps.payments.models import PaymentTransaction
from apps.payments.services import HyperPayService, HyperPayError, PaymentService
from apps.packages.serializers import UserPackageResource


class BaseApiView(APIView):
    pass


class PaymentInfoView(BaseApiView):
    """What the checkout page needs to show the HyperPay widget for the user's own transaction."""

    permission_classes = [IsAuthenticated]

    @api_get('PaymentInfo')
    def get(self, request):
        tx = PaymentTransaction.objects.filter(payment_id=request.query_params.get('id'), user=request.user).first()
        if not tx:
            return send_error('Payment not found', {}, 404)
        checkout_id = (tx.result_summary or {}).get('checkout_id')
        package = tx.package
        return api_response(True, 'Fetched Successfully', {
            'payment_id': tx.payment_id,
            'amount': tx.amount,
            'currency': tx.currency,
            'is_success': tx.is_success,
            'widget_url': HyperPayService.widget_url(checkout_id) if checkout_id and not tx.is_success else None,
            'brands': settings.HYPERPAY_BRANDS,
            'package': {
                'id': package.id,
                'name': package.name,
                'logo': package.logo,
                'period_days': package.period_days,
                'is_custom': package.is_custom,
                'number_of_questions': package.number_of_questions,
            } if package else None,
        })


class ConfirmPaymentView(BaseApiView):
    """
    Called by the result page after the HyperPay widget redirects back. The subscription is granted
    only when HyperPay itself reports the payment as successful for this transaction and amount.
    """

    permission_classes = [IsAuthenticated]

    @api_post('ConfirmPayment')
    def post(self, request):
        payment_id = request.data.get('payment_id')
        if not payment_id:
            return send_error('Validation Errors', {'payment_id': ['This field is required.']}, 422)

        tx = PaymentTransaction.objects.filter(payment_id=payment_id, user=request.user).first()
        if not tx:
            return send_error('Payment not found', {}, 404)

        try:
            status, subscription = PaymentService.verify_and_grant(tx)
        except HyperPayError:
            return send_error('Payment gateway unavailable', {'payment': ['Could not verify the payment, please retry.']}, 503)

        if status == PaymentService.STATUS_PAID:
            return api_response(True, 'Payment confirmed', {
                'status': status,
                'subscription': UserPackageResource(subscription, context={'request': request}).data if subscription else None,
            })
        if status == PaymentService.STATUS_PENDING:
            return api_response(True, 'Payment pending', {'status': status})
        return send_error('Payment failed', {'payment': ['The payment was not completed.'], 'status': [status]}, 402)
