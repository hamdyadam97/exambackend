"""
Login attempt throttling backed by Django's cache.

Limits repeated failed login attempts per phone + IP without touching the
database (uses the default cache, which is local-memory in dev). Successful
logins clear the counter.
"""
from django.core.cache import cache

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 600  # 10 minutes


def _key(phone: str, ip: str) -> str:
    return f'login:attempts:{phone}:{ip}'


def client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


def is_throttled(phone: str, ip: str) -> bool:
    return cache.get(_key(phone, ip), 0) >= MAX_ATTEMPTS


def register_failed_attempt(phone: str, ip: str) -> None:
    key = _key(phone, ip)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, WINDOW_SECONDS)


def clear_attempts(phone: str, ip: str) -> None:
    cache.delete(_key(phone, ip))


def mask_phone(phone: str) -> str:
    """Partially hide a phone number so logs never contain full PII."""
    if phone and len(phone) > 6:
        return f'{phone[:4]}***{phone[-2:]}'
    return '***'
