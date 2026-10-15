"""
Utility helpers.
"""
import re
import random
from django.http import JsonResponse
from rest_framework import serializers
from drf_spectacular.utils import extend_schema


class ApiResponseSerializer(serializers.Serializer):
    """Generic response wrapper used by api_response / send_response / send_error."""
    code = serializers.IntegerField(required=False, help_text='HTTP-like status code')
    status = serializers.BooleanField(help_text='Whether the call succeeded')
    statusCode = serializers.IntegerField(required=False, help_text='Legacy status code')
    message = serializers.CharField(help_text='Human-readable message')
    data = serializers.JSONField(required=False, default=dict, help_text='Payload returned on success')
    errors = serializers.JSONField(required=False, default=dict, help_text='Validation/error details')


def api_get(summary, responses=None, **kwargs):
    """Decorator for GET APIView methods returning the generic response wrapper."""
    schema_responses = {200: ApiResponseSerializer}
    if responses:
        schema_responses.update(responses)
    return extend_schema(summary=summary, responses=schema_responses, **kwargs)


def api_post(summary, request=None, responses=None, **kwargs):
    """Decorator for POST APIView methods returning the generic response wrapper."""
    schema_responses = {
        200: ApiResponseSerializer,
        201: ApiResponseSerializer,
        422: ApiResponseSerializer,
        500: ApiResponseSerializer,
    }
    if responses:
        schema_responses.update(responses)
    return extend_schema(summary=summary, request=request, responses=schema_responses, **kwargs)


def api_response(status=True, message='', data=None, status_code=200, extra=None):
    """Matches BaseController::api_response."""
    response = {
        'code': status_code,
        'status': status,
        'message': message,
        'data': data if data is not None else {},
    }
    if extra:
        response.update(extra)
    return JsonResponse(response, status=status_code, headers={'Cache-Control': 'no-store'})


def send_response(message, result, code=200):
    """Matches BaseController::send_response."""
    return JsonResponse({
        'status': True,
        'statusCode': code,
        'message': message,
        'data': result,
    }, status=code, headers={'Cache-Control': 'no-store'})


def send_error(error, error_messages=None, code=404):
    """Matches BaseController::send_error."""
    response = {
        'status': False,
        'statusCode': code,
        'message': error,
    }
    if error_messages:
        response['errors'] = error_messages
    return JsonResponse(response, status=code, headers={'Cache-Control': 'no-store'})


def generate_otp(digits=6):
    return random.randint(10 ** (digits - 1), 10 ** digits - 1)


def string_number_to_integer(value):
    """Convert Arabic/Persian numerals to English."""
    arabic = '٠١٢٣٤٥٦٧٨٩'
    persian = '۰۱۲۳۴۵۶۷۸۹'
    english = '0123456789'
    for src, dst in [(arabic, english), (persian, english)]:
        value = value.translate(str.maketrans(src, dst))
    return value


def rearrange_tele_input_data(data):
    """Normalize mobile input."""
    dial_code = data.get('dial_code', '')
    mobile_number = data.get('mobile_number', '')
    dial_code = string_number_to_integer(str(dial_code).strip()).lstrip('+')
    mobile_number = string_number_to_integer(str(mobile_number).strip()).lstrip('0')
    if mobile_number:
        data['phone'] = '+' + dial_code + mobile_number
    else:
        # Never fabricate a phone number from an empty mobile input; leave it
        # unset/empty so serializers reject it with a proper required error.
        data.setdefault('phone', '')
    return data


def build_asset_url(request, path_segment, filename):
    if not filename:
        return None
    return request.build_absolute_uri(f'/storage/{path_segment}/{filename}')
