# RootsExams Django Backend

Production-ready Django REST Framework backend for the RootsExams educational platform.

## Features

- JWT authentication with custom User model (phone-based)
- Hierarchical content: self-referential `Category` tree (supports unlimited depth and legacy 3-level data)
- Question bank with answers, topics, and sections
- Exams and exam attempts tracking
- Exam Trails with configurable modes and stages
- Packages and subscriptions with discount codes
- HyperPay payment integration placeholder
- Audit logging and structured logging
- Django Admin with optimized layouts
- API documentation via drf-spectacular (Swagger/ReDoc)

## Tech Stack

- Django 4.2+
- Django REST Framework
- PostgreSQL
- Redis + Celery (optional)
- JWT via djangorestframework-simplejwt

## Setup

### Local Development

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Run server
python manage.py runserver
```

### Docker

```bash
docker-compose up --build
```

### Running Tests

```bash
pytest
# or with Django test runner
python manage.py test
```

## API Documentation

- Swagger UI: `/api/swagger/`
- ReDoc: `/api/redoc/`
- Schema: `/api/schema/`

## App Responsibilities

See [APP_RESPONSIBILITIES.md](./APP_RESPONSIBILITIES.md) for a detailed breakdown of what each app owns.

## Project Structure

```
backend/
├── apps/
│   ├── users/          # Authentication, OTP, profiles
│   ├── content/        # Categories, blogs, notifications
│   ├── exams/          # Questions, exams, trails
│   ├── packages/       # Packages, subscriptions, coupons
│   └── payments/       # Transactions, invoices
├── config/             # Django settings and URLs
├── logs/               # Application logs
└── manage.py
```

## Security Notes

- OTPs are hashed before storage.
- Payment card data is not stored; only gateway tokens are kept.
- Passwords use Django's built-in hashing (PBKDF2 by default).
- Set `DEBUG=False` and configure `ALLOWED_HOSTS` in production.

## License

Private - RootsExams
