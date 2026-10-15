"""
Tests for users app.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from apps.users.models import User, UserProfile, OtpRequest
from apps.users.services import UserService, OtpService


class UserServiceTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        user, otp = UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
            'specialization': 'Medicine',
            'governorate': 'Amman',
            'birth_date': '1990-01-01',
        })
        self.assertEqual(user.phone, '962791234567')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.specialization, 'Medicine')

    def test_login_with_valid_credentials(self):
        user, _ = UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
        })
        logged_in, _ = UserService.login('962791234567', 'securepass123')
        self.assertEqual(logged_in, user)

    def test_login_with_invalid_password(self):
        UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
        })
        logged_in, _ = UserService.login('962791234567', 'wrongpassword')
        self.assertIsNone(logged_in)


class LoginApiTests(TestCase):
    """API-level tests for POST /api/login covering all user-facing outcomes."""

    URL = '/api/login'
    PASSWORD = 'securepass123'

    def _payload(self, mobile='795123456', password=None, dial_code='+962'):
        return {
            'dial_code': dial_code,
            'mobile_number': mobile,
            'password': self.PASSWORD if password is None else password,
        }

    def _create_user(self, phone='+962795123456', status=User.ACTIVE, verified=True, deleted=False):
        user = User.objects.create(
            first_name='John',
            last_name='Doe',
            phone=phone,
            phone_country_code='+962',
            role_type=User.ROLE_USER,
            status=status,
            is_phone_verified=verified,
        )
        user.set_password(self.PASSWORD)
        user.save()
        if deleted:
            user.deleted_at = timezone.now()
            user.save(update_fields=['deleted_at'])
        return user

    def test_missing_fields_returns_422_with_field_errors(self):
        response = self.client.post(
            self.URL,
            data={'dial_code': '+962'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertFalse(body['status'])
        self.assertIn('phone', body['errors'])
        self.assertIn('password', body['errors'])

    def test_wrong_phone_and_wrong_password_are_indistinguishable(self):
        # A user exists, but neither response may reveal which part was wrong.
        self._create_user()
        wrong_phone = self.client.post(
            self.URL, data=self._payload(mobile='711111111'), content_type='application/json'
        ).json()
        wrong_password = self.client.post(
            self.URL, data=self._payload(password='wrongpassword'), content_type='application/json'
        ).json()
        self.assertEqual(wrong_phone, wrong_password)
        self.assertEqual(wrong_phone['statusCode'], 422)
        self.assertIn('WrongCredentials', wrong_phone['errors'])

    def test_successful_login_returns_token_and_user(self):
        self._create_user()
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['status'])
        self.assertIn('token', body['data'])
        self.assertEqual(body['data']['user']['phone'], '+962795123456')

    def test_unverified_phone_redirects_to_otp_verification(self):
        self._create_user(verified=False)
        with patch('apps.users.views.SmsService.send_otp', return_value=True) as send_otp:
            response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['data']['go_to_verify'])
        send_otp.assert_called_once()

    def test_inactive_account_is_blocked_with_generic_safe_message(self):
        self._create_user(status=User.INACTIVE)
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertFalse(body['status'])
        self.assertIn('AccountDisabled', body['errors'])

    def test_soft_deleted_account_is_blocked(self):
        self._create_user(deleted=True)
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertIn('AccountDisabled', response.json()['errors'])


class OtpServiceTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        user, otp = UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
            'specialization': 'Medicine',
            'governorate': 'Amman',
            'birth_date': '1990-01-01',
        })
        self.assertEqual(user.phone, '962791234567')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.specialization, 'Medicine')

    def test_login_with_valid_credentials(self):
        user, _ = UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
        })
        logged_in, _ = UserService.login('962791234567', 'securepass123')
        self.assertEqual(logged_in, user)

    def test_login_with_invalid_password(self):
        UserService.signup({
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '962791234567',
            'password': 'securepass123',
        })
        logged_in, _ = UserService.login('962791234567', 'wrongpassword')
        self.assertIsNone(logged_in)


class OtpServiceTests(TestCase):
    def test_generate_and_verify_otp(self):
        otp = OtpService.generate('962791234567')
        ok, msg = OtpService.verify('962791234567', otp)
        self.assertTrue(ok)

    def test_verify_invalid_otp(self):
        OtpService.generate('962791234567')
        ok, msg = OtpService.verify('962791234567', '000000')
        self.assertFalse(ok)

    def test_expired_otp(self):
        otp = OtpService.generate('962791234567')
        OtpRequest.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))
        ok, msg = OtpService.verify('962791234567', otp)
        self.assertFalse(ok)
