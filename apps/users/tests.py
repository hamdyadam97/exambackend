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

    def test_successful_login_sets_httponly_session_cookie(self):
        self._create_user()
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['status'])
        self.assertTrue(body['data']['authenticated'])
        self.assertEqual(body['data']['user']['phone'], '+962795123456')
        # The token never reaches JavaScript: not in the body, and its cookie is httpOnly.
        self.assertNotIn('token', body['data'])
        self.assertNotIn('refresh', body['data'])
        cookie = response.cookies['access_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')
        self.assertFalse(response.cookies['logged_in']['httponly'])

    def test_cookie_session_reads_and_requires_header_to_write(self):
        self._create_user()
        self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(self.client.get('/api/get-user-info').status_code, 200)
        # Without X-Requested-With a cross-site form could ride the cookie, so the write is not signed in.
        self.assertEqual(self.client.post('/api/update-user-info', {'first_name': 'X'}, content_type='application/json').status_code, 401)
        res = self.client.post(
            '/api/update-user-info', {'first_name': 'X'}, content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(res.status_code, 200)

    def test_logout_clears_the_session(self):
        self._create_user()
        self.client.post(self.URL, data=self._payload(), content_type='application/json')
        res = self.client.post('/api/logout', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.cookies['access_token'].value, '')
        self.assertEqual(self.client.get('/api/get-user-info').status_code, 401)

    def test_stale_cookie_does_not_block_login(self):
        self._create_user()
        self.client.cookies['access_token'] = 'expired-or-forged'
        self.assertEqual(self.client.get('/api/get-user-info').status_code, 401)
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_unverified_phone_redirects_to_otp_verification(self):
        self._create_user(verified=False)
        with patch('apps.core.services.SmsService.send_otp', return_value=True) as send_otp:
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

    def test_repeated_failures_lock_the_phone(self):
        from django.core.cache import cache
        cache.clear()
        self._create_user()
        for _ in range(5):
            self.client.post(self.URL, data=self._payload(password='wrongpassword'), content_type='application/json')
        # Even the right password is refused while locked.
        response = self.client.post(self.URL, data=self._payload(), content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('TooManyAttempts', response.json()['errors'])
        cache.clear()


@patch('apps.core.services.SmsService.send_otp', return_value=True)
class AuthFlowSecurityTests(TestCase):
    """The account-takeover holes found in review must stay closed."""

    PHONE = '+962790000001'

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(phone=self.PHONE, password='OriginalPass123')
        self.user.is_phone_verified = True
        self.user.save()

    def last_otp(self, send_otp):
        return send_otp.call_args[0][1]

    def post(self, url, data):
        return self.client.post(url, data=data, content_type='application/json')

    def test_reset_requires_a_reset_token(self, send_otp):
        res = self.post('/api/reset', {'phone': self.PHONE, 'password': 'attacker-pass', 'password_confirmation': 'attacker-pass'})
        self.assertEqual(res.status_code, 422)
        res = self.post('/api/reset', {
            'phone': self.PHONE, 'reset_token': 'guess', 'password': 'attacker-pass', 'password_confirmation': 'attacker-pass',
        })
        self.assertEqual(res.status_code, 422)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OriginalPass123'))

    def test_full_forgot_password_flow(self, send_otp):
        self.post('/api/forget', {'dial_code': '+962', 'mobile_number': '790000001'})
        otp = self.last_otp(send_otp)
        # The web app sends the phone as `mobile`.
        res = self.post('/api/forget-verify-otp', {'mobile': self.PHONE, 'otp': otp})
        self.assertEqual(res.status_code, 200)
        token = res.json()['data']['reset_token']
        self.assertNotIn('token', res.json()['data'])

        res = self.post('/api/reset', {
            'mobile': self.PHONE, 'reset_token': token, 'password': 'NewPass12345', 'password_confirmation': 'NewPass12345',
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass12345'))
        # A reset ticket works once.
        res = self.post('/api/reset', {
            'mobile': self.PHONE, 'reset_token': token, 'password': 'Again123456', 'password_confirmation': 'Again123456',
        })
        self.assertEqual(res.status_code, 422)

    def test_check_verification_never_returns_a_token(self, send_otp):
        data = self.post('/api/check-verification', {'phone': self.PHONE}).json()['data']
        self.assertNotIn('token', data)
        self.assertFalse(data['go_to_verify'])

    def test_otp_locks_after_three_wrong_codes(self, send_otp):
        self.post('/api/forget', {'dial_code': '+962', 'mobile_number': '790000001'})
        otp = self.last_otp(send_otp)
        wrong = '000000' if otp != '000000' else '111111'
        for _ in range(3):
            self.post('/api/forget-verify-otp', {'mobile': self.PHONE, 'otp': wrong})
        res = self.post('/api/forget-verify-otp', {'mobile': self.PHONE, 'otp': otp})
        self.assertEqual(res.status_code, 429)

    def test_otp_is_not_stored_in_plain_text(self, send_otp):
        self.post('/api/forget', {'dial_code': '+962', 'mobile_number': '790000001'})
        otp = self.last_otp(send_otp)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp)
        self.assertNotEqual(OtpRequest.objects.latest('created_at').otp_hash, otp)

    def test_resend_is_limited_to_once_a_minute(self, send_otp):
        self.post('/api/forget', {'dial_code': '+962', 'mobile_number': '790000001'})
        res = self.post('/api/resend-otp', {'mobile': self.PHONE})
        self.assertEqual(res.status_code, 429)

    def test_signup_then_verify_with_mobile_field(self, send_otp):
        res = self.post('/api/signup', {
            'first_name': 'Sara', 'last_name': 'Ali', 'dial_code': '+962', 'mobile_number': '791111111',
            'password': 'StudentPass1', 'password_confirmation': 'StudentPass1',
            'specialization': 'Nursing', 'governorate': 'Amman', 'birth_date': '2000-01-01',
        })
        self.assertEqual(res.status_code, 200, res.json())
        phone = res.json()['data']['user']['phone']
        res = self.post('/api/verify-otp', {'mobile': phone, 'otp': self.last_otp(send_otp)})
        self.assertEqual(res.status_code, 200, res.json())
        self.assertTrue(res.json()['data']['authenticated'])
        self.assertTrue(res.cookies['access_token']['httponly'])
        self.assertTrue(User.objects.get(phone=phone).is_phone_verified)


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
