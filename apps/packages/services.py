"""
Package and subscription domain services.
"""
from django.db import transaction
from django.utils import timezone
from django.db import models
from apps.packages.models import Package, UserPackage, DiscountCode
from apps.users.services import AuditService


class CouponService:
    """Validates and applies discount codes."""

    @classmethod
    def check_coupon(cls, coupon_code, price, user=None):
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

    @classmethod
    def apply_coupon(cls, coupon_code, price):
        result = cls.check_coupon(coupon_code, price)
        if result['valid']:
            DiscountCode.objects.filter(code=coupon_code).update(used_count=models.F('used_count') + 1)
        return result


class SubscriptionService:
    """Handles package subscriptions."""

    @classmethod
    def subscribe(cls, user, package: Package, price=None, coupon_code=None):
        with transaction.atomic():
            final_price = price if price is not None else package.price
            price_before_discount = package.price
            discount = 0

            if coupon_code:
                result = CouponService.check_coupon(coupon_code, package.price)
                if result['valid']:
                    final_price = result['final_price']
                    price_before_discount = result['price_before_discount']
                    discount = result['discount']

            end_date = None
            if package.period_days:
                end_date = timezone.now().date() + timezone.timedelta(days=package.period_days)

            subscription = UserPackage.objects.create(
                user=user,
                package=package,
                start_date=timezone.now().date(),
                end_date=end_date,
                price=final_price,
                price_before_discount=price_before_discount,
                discount=discount,
            )

            if coupon_code and final_price == 0:
                CouponService.apply_coupon(coupon_code, package.price)

            AuditService.log(
                action='subscription_created',
                entity_type='UserPackage',
                entity_id=subscription.id,
                user=user,
                metadata={'package_id': package.id, 'price': str(final_price)},
            )
            return subscription
