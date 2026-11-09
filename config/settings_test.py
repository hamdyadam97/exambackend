"""
Test settings using SQLite for quick migration validation.
"""
import os

# Tests must not depend on the developer's .env for the key check in settings.py.
os.environ.setdefault('SECRET_KEY', 'test-only-secret-key')
from config.settings import *  # noqa: F401, F403, E402

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_test.sqlite3',  # noqa: F405
    }
}

# The manifest storage needs `collectstatic` to have run; tests render templates without it.
STORAGES = {
    **STORAGES,  # noqa: F405
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
