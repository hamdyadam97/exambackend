"""
Core services: SMS, Coupon, Payments, etc.
"""
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('django')


class SmsService:
    @staticmethod
    def send_otp(mobile, otp):
        if settings.SMS_PROVIDER == 'broadnet' and settings.BROADNET_USER:
            message = f"كود التحقق الخاص بك هو: {otp}"
            try:
                response = requests.get(
                    'https://gwjo1s.broadnet.me:8443/websmpp/websms',
                    params={
                        'user': settings.BROADNET_USER,
                        'pass': settings.BROADNET_PASS,
                        'sid': settings.BROADNET_SID,
                        'mno': mobile,
                        'type': 4,
                        'text': message,
                    },
                    timeout=30,
                )
                logger.info('OTP SMS RESPONSE', extra={'mobile': mobile, 'response': response.text})
                return response.ok
            except Exception as e:
                logger.error('OTP SMS FAILED', extra={'mobile': mobile, 'error': str(e)})
                return False
        logger.warning('SMS provider not configured; OTP not sent.')
        return True  # Allow dev flow


class CouponService:
    @staticmethod
    def check_coupon(coupon_code, price, user=None):
        from apps.packages.models import DiscountCode
        try:
            coupon = DiscountCode.objects.get(
                code=coupon_code,
                status=DiscountCode.STATUS_ACTIVE,
                from_date__lte=timezone.now().date(),
                to_date__gte=timezone.now().date(),
            )
        except DiscountCode.DoesNotExist:
            return {'valid': False, 'message': 'Invalid or expired coupon.'}

        price = float(price)
        if coupon.used_count >= coupon.quantity:
            return {'valid': False, 'message': 'Coupon usage limit reached.'}

        discount = 0
        if coupon.type == DiscountCode.TYPE_PERCENTAGE:
            discount = price * (float(coupon.percentage or 0) / 100)
        elif coupon.type == DiscountCode.TYPE_AMOUNT:
            discount = float(coupon.amount or 0)

        final_price = max(price - discount, 0)
        return {
            'valid': True,
            'discount': discount,
            'price_before_discount': price,
            'final_price': final_price,
            'coupon': coupon_code,
        }


class HyperPayService:
    @staticmethod
    def create_checkout(amount, currency='JOD', payment_type='visa'):
        if not settings.HYPERPAY_ENTITY_ID:
            return {'checkout_id': None, 'url': None, 'error': 'HyperPay not configured'}
        # Placeholder for HyperPay integration.
        return {'checkout_id': None, 'url': None}

    @staticmethod
    def get_payment_status(resource_path):
        return {}


class PhenixBillingService:
    @staticmethod
    def send_invoices_bulk(invoices):
        if not settings.PHENIX_BILLING_URL:
            return {'sent': False, 'error': 'Phenix URL not configured'}
        # Placeholder for Phenix integration.
        return {'sent': True, 'count': len(invoices)}


class OpenAiService:
    @staticmethod
    def explain_question(question_text, selected_answer, correct_answer, notes=''):
        if not settings.OPENAI_API_KEY:
            return None
        prompt = f"""Question: {question_text}\nSelected answer: {selected_answer}\nCorrect answer: {correct_answer}\nExplain why the correct answer is right."""
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': settings.OPENAI_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 500,
                },
                timeout=30,
            )
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error('OpenAI request failed', extra={'error': str(e)})
            return None
