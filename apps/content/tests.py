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


class TaxonomySeedTests(TestCase):
    def test_seed_builds_a_clean_tree_and_is_idempotent(self):
        from django.core.management import call_command
        from apps.content.models import Category, ExamSection, QuestionsTopic
        from apps.content.taxonomy import SECTIONS

        handmade = Category.objects.create(name='SMLE- prometric', status=Category.INACTIVE)
        untouched = Category.objects.create(name='UWORLD')
        call_command('seed_taxonomy', verbosity=0)
        handmade.refresh_from_db()
        self.assertEqual(handmade.name, 'SMLE - Prometric')  # renamed in place, not duplicated
        self.assertEqual(handmade.status, Category.INACTIVE)
        self.assertEqual(Category.objects.filter(name='SMLE - Prometric').count(), 1)
        self.assertTrue(handmade.children.filter(name='SMLE - Nursing').exists())
        self.assertTrue(Category.objects.filter(pk=untouched.pk, name='UWORLD').exists())
        counts = (Category.objects.count(), ExamSection.objects.count(), QuestionsTopic.objects.count())
        call_command('seed_taxonomy', verbosity=0)
        self.assertEqual(counts, (Category.objects.count(), ExamSection.objects.count(), QuestionsTopic.objects.count()))

        # Every branch is three levels deep, so the exam builder never stops at an empty step.
        for sub in Category.objects.filter(level=Category.LEVEL_SUB_CATEGORY):
            self.assertTrue(sub.children.exists(), sub.name)
        self.assertFalse(Category.objects.filter(name__regex=r'(4th|5th|6th) Year|Free Trial|20\d\d Exam').exists())

        # A topic belongs to exactly one section.
        all_topics = [t for topics in SECTIONS.values() for t in topics]
        self.assertEqual(len(all_topics), len(set(all_topics)))
        self.assertEqual(QuestionsTopic.objects.get(topic='Pneumonia').section.name, 'Respiratory System')
        self.assertFalse(QuestionsTopic.objects.filter(section__isnull=True).exists())


class SharedSectionTests(TestCase):
    """Sections without a category are shared by every exam and listed where they have questions."""

    def test_shared_section_listed_with_its_topics(self):
        from rest_framework.test import APIClient
        from apps.content.models import Category, ExamSection, QuestionsTopic
        from apps.exams.models import ExamSectionLink, Question, QuestionTopic

        user = User.objects.create_user(phone='+962790000009', password='x' * 10)
        client = APIClient()
        client.force_authenticate(user)
        jmc = Category.objects.create(name='JMC')
        other = Category.objects.create(name='USMLE')
        resp = ExamSection.objects.create(name='Respiratory System')
        ExamSection.objects.create(name='Cardiovascular System')  # no questions: hidden
        pneumonia = QuestionsTopic.objects.create(topic='Pneumonia', section=resp)
        q = Question.objects.create(text_question='q', category=jmc, status=1)
        ExamSectionLink.objects.create(question=q, section=resp)
        QuestionTopic.objects.create(question=q, topic=pneumonia)

        data = client.get(f'/api/exams/sections?category_ids[]={jmc.id}').json()['data']
        self.assertEqual([s['name'] for s in data['sections']], ['Respiratory System'])
        self.assertEqual(data['total_questions'], 1)
        self.assertEqual(client.get(f'/api/exams/sections?category_ids[]={other.id}').json()['data']['sections'], [])

        topics = client.get(f'/api/exams/topics?section_ids[]={resp.id}&category_ids[]={jmc.id}').json()['data']['topics']
        self.assertEqual([(t['name'], t['section_id']) for t in topics], [('Pneumonia', resp.id)])
