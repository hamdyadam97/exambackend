"""
Development settings for quick Swagger/local testing using a file-based SQLite DB.
"""
from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_dev.sqlite3',
    }
}

# Allow local frontend + Swagger UI
CORS_ALLOW_ALL_ORIGINS = True
