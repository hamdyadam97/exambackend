"""
Session token in an httpOnly cookie.

The browser never sees the JWT: login sets it in an httpOnly, SameSite=Strict cookie, so injected
scripts cannot read it. A second, readable `logged_in` cookie only tells the frontend that a session
exists. Because a cookie is sent automatically, requests that change data only count as signed in
when they carry the X-Requested-With header, which another site cannot add without passing our CORS rules.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import AccessToken

AUTH_COOKIE = 'access_token'
FLAG_COOKIE = 'logged_in'
CSRF_HEADER = 'HTTP_X_REQUESTED_WITH'
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class CookieJWTAuthentication(JWTAuthentication):
    """Bearer header first (API clients), then the httpOnly cookie (the website)."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        raw = request.COOKIES.get(AUTH_COOKIE)
        if not raw:
            return None
        # A write without the header may come from another site riding the cookie: treat it as anonymous.
        if request.method not in SAFE_METHODS and request.META.get(CSRF_HEADER) != 'XMLHttpRequest':
            return None
        try:
            validated = self.get_validated_token(raw)
            user = self.get_user(validated)
        except (InvalidToken, AuthenticationFailed):
            # A stale cookie must not break public endpoints such as login; protected ones still answer 401.
            return None
        return user, validated


def _cookie_options():
    return {'path': '/', 'secure': not settings.DEBUG, 'samesite': 'Strict'}


def login_response(response, user):
    """Attach a fresh session to `response` for `user`."""
    token = AccessToken.for_user(user)
    max_age = int(token.lifetime.total_seconds())
    response.set_cookie(AUTH_COOKIE, str(token), max_age=max_age, httponly=True, **_cookie_options())
    response.set_cookie(FLAG_COOKIE, '1', max_age=max_age, httponly=False, **_cookie_options())
    return response


def session_payload(user):
    """Public part of a new session, returned in the response body instead of the token."""
    return {
        'authenticated': True,
        'token_expired_at': timezone.now() + AccessToken.lifetime,
    }


def logout_response(response):
    for name in (AUTH_COOKIE, FLAG_COOKIE):
        response.delete_cookie(name, path='/', samesite='Strict')
    return response
