"""
Test settings using SQLite for quick migration validation.
"""
from config.settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_test.sqlite3',  # noqa: F405
    }
}
