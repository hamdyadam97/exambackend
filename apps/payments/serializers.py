"""
Payment serializers.
"""
from rest_framework import serializers
from apps.payments.models import PaymentType, Invoice, PaymentTransaction, MoneyLog


class PaymentTypeResource(serializers.ModelSerializer):
    class Meta:
        model = PaymentType
        fields = ['id', 'name', 'status']


class InvoiceResource(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'


class PaymentTransactionResource(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = '__all__'


class MoneyLogResource(serializers.ModelSerializer):
    class Meta:
        model = MoneyLog
        fields = '__all__'
