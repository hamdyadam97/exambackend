"""
Core middleware for logging, security, and error handling.
"""
import logging
import traceback
from django.http import JsonResponse

logger = logging.getLogger('api')


class ExceptionLoggingMiddleware:
    """Logs unhandled exceptions and returns JSON responses for API requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        logger.error(
            'Unhandled exception: %s\n%s',
            str(exception),
            traceback.format_exc(),
            extra={
                'path': request.path,
                'method': request.method,
                'user_id': getattr(request.user, 'id', None),
            },
        )
        if request.path.startswith('/api/'):
            return JsonResponse(
                {'status': False, 'statusCode': 500, 'message': 'Internal server error.'},
                status=500,
            )
        return None


class SecurityHeadersMiddleware:
    """Adds common security headers to responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
