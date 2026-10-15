"""
Payment API views.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from apps.core.utils import api_response, send_error, api_get, api_post
from apps.payments.models import PaymentTransaction, MoneyLog
from apps.packages.models import UserPackage
from apps.packages.serializers import UserPackageResource


class BaseApiView(APIView):
    pass


class PaymentCallbackView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('PaymentCallback')
    def post(self, request):
        # Placeholder for HyperPay callback
        return api_response(True, 'Payment callback received', {})


class PaymentStatusView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('PaymentStatus')
    def get(self, request):
        # Placeholder for HyperPay status check
        return api_response(True, 'Payment status', {'status': 'pending'})


class PaymentInfoView(BaseApiView):
    """Details of the current user's pending payment transaction."""

    permission_classes = [IsAuthenticated]

    @api_get('PaymentInfo')
    def get(self, request):
        payment_id = request.query_params.get('id')
        tx = PaymentTransaction.objects.filter(payment_id=payment_id, user=request.user).first()
        if not tx:
            return send_error('Payment not found', {}, 404)
        package = tx.package
        return api_response(True, 'Fetched Successfully', {
            'payment_id': tx.payment_id,
            'amount': tx.amount,
            'currency': tx.currency,
            'is_success': tx.is_success,
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
    """Completes a pending payment transaction and grants the subscription.

    This backs the built-in checkout page while no external gateway is
    configured; when HyperPay is live, its callback performs the same grant.
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

        if tx.is_success:
            sub = UserPackage.objects.filter(user=request.user, package=tx.package).order_by('-created_at').first()
            if sub:
                return api_response(True, 'Payment already confirmed', {
                    'subscription': UserPackageResource(sub, context={'request': request}).data,
                })
            return send_error('Payment already confirmed but no subscription found', {}, 422)

        package = tx.package
        if not package:
            return send_error('Package no longer available', {}, 422)

        info = tx.result_summary or {}
        custom_days = info.get('custom_days')
        if package.is_custom and custom_days:
            period_days = int(custom_days)
        else:
            period_days = int(info.get('period_days') or package.period_days or 0)

        sub = UserPackage.objects.create(
            user=request.user,
            package=package,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=period_days),
            price=tx.amount,
        )
        tx.is_success = True
        tx.gateway_transaction_id = f'SIM-{payment_id}'
        tx.result_summary = {**info, 'confirmed_at': timezone.now().isoformat()}
        tx.save(update_fields=['is_success', 'gateway_transaction_id', 'result_summary', 'updated_at'])

        MoneyLog.objects.create(
            user=request.user,
            platform=MoneyLog.PLATFORM_WEB,
            item=package,
            payment_id=payment_id,
            status=1,
            coupon_code=info.get('coupon'),
        )

        return api_response(True, 'Payment confirmed', {
            'subscription': UserPackageResource(sub, context={'request': request}).data,
        })
