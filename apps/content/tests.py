"""
Tests for content app.
"""
from django.test import TestCase

from apps.content.models import Faq, Partner, Setting
from apps.exams.models import ExamTrail
from apps.users.models import User


class LandingApiTests(TestCase):
    def get(self):
        res = self.client.get('/api/landing/index')
        self.assertEqual(res.status_code, 200)
        return res.json()['data']

    def test_stats_are_computed_from_real_data(self):
        student = User.objects.create_user(phone='+962790000001', password='x' * 10)
        Partner.objects.create(name='MOH', status=Partner.ACTIVE)
        ExamTrail.objects.create(user=student, title='a', status='completed', total_questions=10, correct_answers=8)
        ExamTrail.objects.create(user=student, title='b', status='completed', total_questions=10, correct_answers=2)

        stats = self.get()['stats']
        self.assertEqual(stats, {'students': 1, 'attempts': 2, 'pass_rate': 50, 'partners': 1})

    def test_admin_settings_override_stats_and_map(self):
        Setting.objects.create(key='home_stat_students', value='50000')
        Setting.objects.create(key='home_stat_pass_rate', value='not a number')
        Setting.objects.create(key='home_map_cities', value='Amman, Irbid ,')

        data = self.get()
        self.assertEqual(data['stats']['students'], 50000)
        self.assertEqual(data['stats']['pass_rate'], 0)  # Invalid override falls back to the real value.
        self.assertEqual(data['map_cities'], ['Amman', 'Irbid'])

    def test_only_active_faqs_in_order(self):
        Faq.objects.create(question='Second', answer='b', order=2)
        Faq.objects.create(question='First', answer='a', order=1)
        Faq.objects.create(question='Hidden', answer='c', status=Faq.INACTIVE)
        self.assertEqual([f['question'] for f in self.get()['faqs']], ['First', 'Second'])
