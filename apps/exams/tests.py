"""
Tests for exams app.
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User
from apps.content.models import Category
from apps.exams.models import Question, Answer, ExamTrail
from apps.exams.services import ExamTrailService
from apps.packages.models import Package, UserPackage


def subscribe(user, category):
    """An active package subscription opening `category` (exams only draw from subscribed categories)."""
    package = Package.objects.create(name=f'Package {category.name}', category=category, period_days=30)
    today = timezone.now().date()
    return UserPackage.objects.create(user=user, package=package, start_date=today, end_date=today + timedelta(days=30))


class ExamTrailServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.category = Category.objects.create(name='Test Category')
        subscribe(self.user, self.category)
        self.question = Question.objects.create(text_question='Q1', category=self.category)

    def test_create_trail(self):
        trail = ExamTrailService.create_trail(self.user, {
            'title': 'My Trail',
            'exam_mode': 'tatur',
            'question_mode': 'all',
            'is_timed_mode': False,
            'question_count': 1,
            'categories': [self.category.id],
            'sub_categories': [],
            'sub_sub_categories': [],
            'sections': [],
        })
        self.assertEqual(trail.user, self.user)
        self.assertEqual(trail.categories.count(), 1)

    def test_record_answer(self):
        trail = ExamTrail.objects.create(user=self.user, title='T', question_count=1)
        detail = ExamTrailService.record_answer(trail, self.question.id, is_correct=True)
        self.assertTrue(detail.is_correct)
        trail.refresh_from_db()
        self.assertEqual(trail.correct_answers, 1)


class AnswerIntegrityTests(TestCase):
    """The correct answer must never reach the client early, and the client must not grade itself."""

    def setUp(self):
        from apps.exams.models import ExamTrialDetail

        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        category = Category.objects.create(name='Surgery')
        subscribe(self.user, category)
        self.question = Question.objects.create(text_question='Q', category=category, status=1, notes='Because.')
        self.right = Answer.objects.create(question=self.question, answer_option='right')
        self.wrong = Answer.objects.create(question=self.question, answer_option='wrong')
        self.question.correct_answer = self.right
        self.question.save()
        other = Question.objects.create(text_question='Other', category=category, status=1)
        self.foreign_answer = Answer.objects.create(question=other, answer_option='x')

        self.exam_trail = ExamTrail.objects.create(user=self.user, title='E', mode=ExamTrail.MODE_EXAM, question_count=1)
        self.tutor_trail = ExamTrail.objects.create(user=self.user, title='T', mode=ExamTrail.MODE_TUTOR, question_count=1)
        for trail in (self.exam_trail, self.tutor_trail):
            ExamTrialDetail.objects.create(exam_trail=trail, question=self.question)

    def get_question(self, trail):
        return self.client.get(f'/api/exams/{self.question.id}/get-question?exam_id={trail.id}')

    def answer(self, trail, answer, **extra):
        return self.client.post(
            f'/api/exams/{trail.id}/store-single-question-answer',
            {'question_id': self.question.id, 'answer_id': answer.id, **extra},
            format='json',
        )

    def test_question_requires_its_exam(self):
        self.assertEqual(self.client.get(f'/api/exams/{self.question.id}/get-question').status_code, 404)

    def test_exam_mode_hides_correct_answer_until_submitted(self):
        question = self.get_question(self.exam_trail).json()['data']['question']
        self.assertIsNone(question['correct_answer_id'])
        self.assertIsNone(question['notes'])

        self.client.post(f'/api/exams/{self.exam_trail.id}/finish')
        question = self.get_question(self.exam_trail).json()['data']['question']
        self.assertEqual(question['correct_answer_id'], self.right.id)

    def test_client_cannot_grade_its_own_answer(self):
        res = self.answer(self.exam_trail, self.wrong, is_correct=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()['data']['is_correct'])
        self.assertFalse(self.exam_trail.details.get().is_correct)

    def test_exam_mode_hides_grading_while_in_progress(self):
        self.answer(self.exam_trail, self.right)
        data = self.client.get(f'/api/exams/get-questions?exam_id={self.exam_trail.id}').json()['data']
        self.assertIsNone(data['details'][0]['is_correct'])
        self.assertIsNone(data['exam']['correct_answers'])
        self.assertEqual(self.client.get(f'/api/exams/{self.exam_trail.id}/get').status_code, 409)

        self.client.post(f'/api/exams/{self.exam_trail.id}/finish')
        exam = self.client.get(f'/api/exams/{self.exam_trail.id}/get').json()['data']['exam']
        self.assertEqual(exam['correct_answers'], 1)

    def test_tutor_mode_reveals_only_after_answering(self):
        self.assertIsNone(self.get_question(self.tutor_trail).json()['data']['question']['correct_answer_id'])
        res = self.answer(self.tutor_trail, self.wrong).json()['data']
        self.assertFalse(res['is_correct'])
        self.assertEqual(res['correct_answer_id'], self.right.id)
        self.assertEqual(res['notes'], 'Because.')
        self.assertEqual(self.get_question(self.tutor_trail).json()['data']['question']['correct_answer_id'], self.right.id)

    def test_answer_from_another_question_is_rejected(self):
        self.assertEqual(self.answer(self.exam_trail, self.foreign_answer).status_code, 422)


class QuestionCollectionTests(AnswerIntegrityTests):
    """Reuses the integrity fixture: one question in an exam-mode trail and one in a tutor-mode trail."""

    def test_save_and_unsave(self):
        url = f'/api/questions/{self.question.id}/save'
        self.assertEqual(self.client.post(url).status_code, 200)
        saved = self.client.get('/api/questions/collection/saved').json()['data']['questions']
        self.assertEqual([q['id'] for q in saved], [self.question.id])
        self.assertEqual(saved[0]['text'], 'Q')

        data = self.client.get(f'/api/exams/get-questions?exam_id={self.exam_trail.id}').json()['data']
        self.assertEqual(data['saved_question_ids'], [self.question.id])

        self.client.delete(url)
        self.assertEqual(self.client.get('/api/questions/collection/saved').json()['data']['questions'], [])

    def test_cannot_save_question_outside_own_exams(self):
        self.assertEqual(self.client.post(f'/api/questions/{self.foreign_answer.question_id}/save').status_code, 404)

    def test_wrong_list_ignores_exams_in_progress(self):
        self.answer(self.exam_trail, self.wrong)
        self.assertEqual(self.client.get('/api/questions/collection/wrong').json()['data']['questions'], [])
        self.client.post(f'/api/exams/{self.exam_trail.id}/finish')
        wrong = self.client.get('/api/questions/collection/wrong').json()['data']['questions']
        self.assertEqual(wrong[0]['times_wrong'], 1)

    def test_flag_and_review_persist(self):
        res = self.client.post(
            f'/api/exams/{self.exam_trail.id}/question-state',
            {'question_id': self.question.id, 'is_marked': True, 'is_review': True}, format='json',
        )
        self.assertEqual(res.json()['data'], {'question_id': self.question.id, 'is_marked': True, 'is_review': True})
        detail = self.client.get(f'/api/exams/get-questions?exam_id={self.exam_trail.id}').json()['data']['details'][0]
        self.assertTrue(detail['is_marked'])
        self.assertTrue(detail['is_review'])
        flagged = self.client.get('/api/questions/collection/flagged').json()['data']['questions']
        self.assertEqual([q['id'] for q in flagged], [self.question.id])

    def test_build_exam_from_saved_questions(self):
        self.client.post(f'/api/questions/{self.question.id}/save')
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'tatur', 'question_mode': 'saved', 'question_count': 10,
            'categories': [self.question.category_id],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        trail = ExamTrail.objects.get(pk=res.json()['data']['exam_id'])
        self.assertEqual(list(trail.details.values_list('question_id', flat=True)), [self.question.id])


class DifficultyFilterTests(TestCase):
    def setUp(self):
        from apps.content.models import ExamSection
        from apps.exams.models import ExamSectionLink

        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Pediatrics')
        subscribe(self.user, self.category)
        self.section = ExamSection.objects.create(name='Neonates', category=self.category)
        self.by_level = {}
        for level, count in ((Question.DIFFICULTY_EASY, 2), (Question.DIFFICULTY_HARD, 3), (None, 1)):
            for i in range(count):
                q = Question.objects.create(text_question=f'{level}-{i}', category=self.category, status=1, difficulty=level)
                ExamSectionLink.objects.create(question=q, section=self.section)
                self.by_level.setdefault(level, []).append(q.id)

    def section_total(self, difficulty=''):
        url = f'/api/exams/sections?category_ids[]={self.category.id}'
        if difficulty:
            url += f'&difficulty={difficulty}'
        return self.client.get(url).json()['data']

    def test_counts_follow_difficulty(self):
        self.assertEqual(self.section_total()['total_questions'], 6)
        self.assertEqual(self.section_total('mixed')['total_questions'], 6)
        self.assertEqual(self.section_total('hard')['total_questions'], 3)
        data = self.section_total('easy')
        self.assertEqual(data['total_questions'], 2)
        self.assertEqual(data['sections'][0]['questions_count'], 2)

    def test_exam_draws_only_chosen_difficulty(self):
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'difficulty': 'hard', 'question_count': 10,
            'categories': [self.category.id], 'sections': [self.section.id],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        trail = ExamTrail.objects.get(pk=res.json()['data']['exam_id'])
        self.assertEqual(trail.difficulty, Question.DIFFICULTY_HARD)
        self.assertEqual(sorted(trail.details.values_list('question_id', flat=True)), sorted(self.by_level[Question.DIFFICULTY_HARD]))

    def create(self, **options):
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'question_count': 10, 'categories': [self.category.id], **options,
        }, format='json')
        return ExamTrail.objects.get(pk=res.json()['data']['exam_id'])

    def test_questions_in_fixed_order_when_not_randomized(self):
        trail = self.create(randomize_questions=False)
        ids = list(trail.details.order_by('id').values_list('question_id', flat=True))
        self.assertEqual(ids, sorted(ids))

    def test_answer_order_is_shuffled_per_exam_and_stable(self):
        question = Question.objects.get(pk=self.by_level[None][0])
        answers = [Answer.objects.create(question=question, answer_option=str(i)).id for i in range(6)]
        url = f'/api/exams/{question.id}/get-question?exam_id='

        plain = self.create()
        shown = [a['id'] for a in self.client.get(url + str(plain.id)).json()['data']['question']['answers']]
        self.assertEqual(shown, answers)

        shuffled = self.create(randomize_answers=True)
        first = [a['id'] for a in self.client.get(url + str(shuffled.id)).json()['data']['question']['answers']]
        again = [a['id'] for a in self.client.get(url + str(shuffled.id)).json()['data']['question']['answers']]
        self.assertEqual(sorted(first), answers)
        self.assertEqual(first, again)
        self.assertEqual(first, shuffled.answer_order(question.id, answers))

    def test_no_questions_at_difficulty(self):
        Question.objects.filter(difficulty=Question.DIFFICULTY_EASY).update(difficulty=Question.DIFFICULTY_HARD)
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'difficulty': 'easy', 'question_count': 5, 'categories': [self.category.id],
        }, format='json')
        self.assertEqual(res.status_code, 500)
        self.assertFalse(res.json()['status'])


class ExamTimeLimitTests(TestCase):
    """A timed 30-minute exam with 3 questions, built by the student."""

    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Nursing')
        subscribe(self.user, self.category)
        self.questions = [
            Question.objects.create(text_question=f'Q{i}', category=self.category, status=1) for i in range(3)
        ]

    def start_trail(self, minutes_ago=0):
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'is_timed_mode': True, 'duration_minutes': 30,
            'question_count': 3, 'categories': [self.category.id],
        }, format='json')
        trail_id = res.json()['data']['exam_id']
        ExamTrail.objects.filter(pk=trail_id).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
        return trail_id

    def answer(self, trail_id):
        question_id = ExamTrail.objects.get(pk=trail_id).details.order_by('id').first().question_id
        return self.client.post(
            f'/api/exams/{trail_id}/store-single-question-answer',
            {'question_id': question_id, 'answer_id': None, 'is_correct': True},
            format='json',
        )

    def test_remaining_time_comes_from_the_server(self):
        trail_id = self.start_trail(minutes_ago=10)
        exam = self.client.get(f'/api/exams/get-questions?exam_id={trail_id}').json()['data']['exam']
        self.assertEqual(exam['duration'], 30)
        self.assertTrue(19 * 60 < exam['remaining_seconds'] <= 20 * 60)

    def test_answer_accepted_before_deadline(self):
        self.assertEqual(self.answer(self.start_trail(minutes_ago=29)).status_code, 200)

    def test_answer_after_deadline_is_rejected_and_exam_is_submitted(self):
        trail_id = self.start_trail(minutes_ago=31)
        res = self.answer(trail_id)
        self.assertEqual(res.status_code, 409)
        self.assertIn('TimeUp', res.json()['errors'])
        self.assertEqual(ExamTrail.objects.get(pk=trail_id).status, 'completed')

    def test_answer_after_finishing_is_rejected(self):
        trail_id = self.start_trail()
        self.client.post(f'/api/exams/{trail_id}/finish')
        res = self.answer(trail_id)
        self.assertEqual(res.status_code, 409)
        self.assertIn('ExamFinished', res.json()['errors'])

    def test_opening_an_expired_exam_submits_it(self):
        trail_id = self.start_trail(minutes_ago=31)
        exam = self.client.get(f'/api/exams/get-questions?exam_id={trail_id}').json()['data']['exam']
        self.assertEqual(exam['status'], 'completed')
        self.assertEqual(exam['remaining_seconds'], 0)

    def test_custom_exam_keeps_chosen_duration(self):
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'is_timed_mode': True, 'duration_minutes': 45,
            'question_count': 2, 'categories': [self.category.id],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(ExamTrail.objects.get(pk=res.json()['data']['exam_id']).duration_minutes, 45)

    def test_ready_made_exam_endpoints_are_gone(self):
        self.assertEqual(self.client.get('/api/exams').status_code, 404)
        self.assertEqual(self.client.post('/api/exams/1/start').status_code, 404)


class StudentInsightsApiTests(TestCase):
    def setUp(self):
        from apps.content.models import QuestionsTopic
        from apps.exams.models import QuestionTopic, ExamTrialDetail

        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Pharmacy')
        UserPackage.objects.create(
            user=self.user,
            package=Package.objects.create(name='Pharma', category=self.category, number_of_questions=100),
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
        )
        self.strong = QuestionsTopic.objects.create(topic='Dosage', category=self.category)
        self.weak = QuestionsTopic.objects.create(topic='Toxicology', category=self.category)
        QuestionsTopic.objects.create(topic='Untouched', category=self.category)

        trail = ExamTrail.objects.create(
            user=self.user, title='Pharma 1', question_count=8,
            status='completed', total_questions=8, correct_answers=4,
        )
        # 4/4 correct on the strong topic, 0/4 on the weak one.
        for i in range(8):
            topic, correct = (self.strong, True) if i < 4 else (self.weak, False)
            q = Question.objects.create(text_question=f'Q{i}', category=self.category, status=1)
            answer = Answer.objects.create(question=q, answer_option='a')
            QuestionTopic.objects.create(question=q, topic=topic)
            ExamTrialDetail.objects.create(exam_trail=trail, question=q, answer=answer, is_correct=correct)

    def test_insights(self):
        res = self.client.get('/api/dashboard/insights')
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']

        self.assertEqual(data['score_history'][0]['score'], 50)
        self.assertEqual(data['categories'][0], {
            'id': self.category.id, 'name': 'Pharmacy', 'answered': 8, 'accuracy': 50,
        })
        self.assertEqual([t['name'] for t in data['topics']['strong']], ['Dosage'])
        self.assertEqual([t['name'] for t in data['topics']['weak']], ['Toxicology'])
        self.assertEqual([t['name'] for t in data['topics']['untouched']], ['Untouched'])
        self.assertEqual(data['wrong_questions'], 4)
        self.assertEqual(data['achievements']['passed_exams'], 1)
        self.assertEqual(data['achievements']['current_streak'], 1)
        self.assertEqual(sum(d['correct'] for d in data['daily_activity']), 4)
        self.assertEqual(data['subscription']['questions_used'], 8)
        self.assertIsNone(data['in_progress'])

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get('/api/dashboard/insights').status_code, (401, 403))


class ImportQuestionsTests(TestCase):
    """manage.py import_questions: the cleaned bank from the old platform."""

    def setUp(self):
        import json
        import tempfile
        from django.core.management import call_command

        call_command('seed_taxonomy', verbosity=0)
        path = ['Residency Entrance - Medicine', 'Royal Medical Services (RMS)']
        self.records = [
            {'source_id': 1, 'text': '<p>Q1</p>', 'options': ['<p>a</p>', '<p>b</p>', '<p>All of the above</p>'],
             'correct': 2, 'explanation': '<p>why</p>', 'hint': None, 'path': path + ['Surgery'], 'exam_year': 2024,
             'active_before': True, 'problems': [], 'fixed_order': True,
             'section': 'General Surgery', 'topic': 'Hernia'},
            {'source_id': 2, 'text': '<p>Q2</p>', 'options': ['<p>a</p>', '<p>b</p>'], 'correct': None,
             'explanation': None, 'hint': None, 'path': path + [None], 'exam_year': None, 'active_before': True,
             'problems': ['No correct answer was set on the old platform.'], 'fixed_order': False},
        ]
        self.file = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(self.records, self.file)
        self.file.close()
        self.call = lambda: call_command('import_questions', self.file.name, verbosity=0)

    def test_import_is_complete_and_rerunnable(self):
        from apps.exams.models import ExamSectionLink, QuestionTopic

        self.call()
        self.call()
        self.assertEqual(Question.objects.count(), 2)
        good = Question.objects.get(source_id=1)
        self.assertEqual(good.status, Question.ACTIVE)
        self.assertFalse(good.needs_review)
        self.assertEqual(good.sub_subcategory.name, 'Surgery')
        self.assertEqual(good.sub_subcategory.parent.name, 'Royal Medical Services (RMS)')
        self.assertEqual(good.correct_answer.answer_option, '<p>All of the above</p>')
        self.assertEqual([a.answer_option for a in good.answers.all()], self.records[0]['options'])
        self.assertEqual((good.exam_year, good.keep_answer_order, good.notes), (2024, True, '<p>why</p>'))
        self.assertTrue(ExamSectionLink.objects.filter(question=good, section__name='General Surgery').exists())
        self.assertTrue(QuestionTopic.objects.filter(question=good, topic__topic='Hernia').exists())

        broken = Question.objects.get(source_id=2)
        self.assertEqual(broken.status, Question.INACTIVE)
        self.assertTrue(broken.needs_review)
        self.assertIn('No correct answer', broken.review_note)
        self.assertIsNone(broken.sub_subcategory)

    def test_fixed_order_question_is_never_shuffled(self):
        self.call()
        user = User.objects.create_user(phone='962791234500', password='pass')
        client = APIClient()
        client.force_authenticate(user)
        q = Question.objects.get(source_id=1)
        trail = ExamTrail.objects.create(user=user, title='t', shuffle_answers=True)
        trail.details.create(question=q)
        shown = client.get(f'/api/exams/{q.id}/get-question?exam_id={trail.id}').json()['data']['question']['answers']
        self.assertEqual([a['id'] for a in shown], list(q.answers.values_list('id', flat=True)))


class SeedPruneTests(TestCase):
    def test_prune_removes_only_unused_categories(self):
        from django.core.management import call_command

        stale = Category.objects.create(name='MOH Open Recruitment')
        Category.objects.create(name='Medicine', parent=stale, level=2)
        used = Category.objects.create(name='Old exam')
        Question.objects.create(text_question='q', category=used)
        kept = Category.objects.create(name='Free Trial (20 questions)')
        call_command('seed_taxonomy', '--prune', verbosity=0)
        self.assertFalse(Category.objects.filter(name__in=['MOH Open Recruitment', 'Medicine']).exists())
        self.assertTrue(Category.objects.filter(pk=used.pk).exists())
        self.assertTrue(Category.objects.filter(pk=kept.pk).exists())
        self.assertTrue(Category.objects.filter(name='Medical Students', parent=None).exists())


class NoSectionsYetTests(TestCase):
    """Imported questions not filed under a section can still be used: the whole path is drawn."""

    def test_path_without_sections_counts_and_builds(self):
        user = User.objects.create_user(phone='962791234501', password='pass')
        client = APIClient()
        client.force_authenticate(user)
        root = Category.objects.create(name='JMC')
        subscribe(user, root)
        for i in range(3):
            Question.objects.create(text_question=f'q{i}', category=root, status=1)
        data = client.get(f'/api/exams/sections?category_ids[]={root.id}').json()['data']
        self.assertEqual((data['sections'], data['total_questions']), ([], 3))
        res = client.post('/api/exams/store', {'exam_mode': 'exam', 'question_count': 10, 'categories': [root.id]}, format='json')
        self.assertEqual(res.status_code, 200, res.json())
        self.assertEqual(ExamTrail.objects.get(pk=res.json()['data']['exam_id']).details.count(), 3)


class SubscriptionAccessTests(TestCase):
    """Exams only draw from the categories the student's active packages open."""

    def setUp(self):
        self.user = User.objects.create_user(phone='962791234502', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.board = Category.objects.create(name='Board')
        self.urology = Category.objects.create(name='Urology', parent=self.board, level=2)
        self.surgery = Category.objects.create(name='Surgery', parent=self.board, level=2)
        self.other = Category.objects.create(name='SMLE')
        for sub, n in ((self.urology, 2), (self.surgery, 3)):
            for i in range(n):
                Question.objects.create(text_question=f'{sub.name}{i}', category=self.board, sub_category=sub, status=1)
        Question.objects.create(text_question='smle', category=self.other, status=1)

    def store(self, categories, **extra):
        return self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'question_count': 50, 'categories': categories, **extra}, format='json')

    def roots(self):
        return [c['name'] for c in self.client.get('/api/exams/create').json()['data']['categories']]

    def test_no_subscription_no_questions(self):
        self.assertEqual(self.roots(), [])
        res = self.store([self.other.id])
        self.assertFalse(res.json()['status'])
        self.assertFalse(ExamTrail.objects.filter(details__isnull=False).exists())

    def test_sub_category_package_opens_only_that_sub_category(self):
        subscribe(self.user, self.urology)
        self.assertEqual(self.roots(), ['Board'])
        subs = self.client.get(f'/api/exams/subcategories?category_ids[]={self.board.id}').json()['data']['sub_categories']
        self.assertEqual([s['name'] for s in subs], ['Urology'])
        # Even asking for the whole category (or another one) only draws the subscribed questions.
        res = self.store([self.board.id, self.other.id])
        trail = ExamTrail.objects.get(pk=res.json()['data']['exam_id'])
        self.assertEqual(set(trail.details.values_list('question__sub_category', flat=True)), {self.urology.id})
        self.assertEqual(trail.details.count(), 2)

    def test_expired_subscription_closes_access(self):
        sub = subscribe(self.user, self.other)
        sub.end_date = timezone.now().date() - timedelta(days=1)
        sub.save()
        self.assertEqual(self.roots(), [])

    def test_staff_sees_everything(self):
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(sorted(self.roots()), ['Board', 'SMLE'])


class KeywordClassifierTests(TestCase):
    def test_files_questions_by_field_and_keywords(self):
        from apps.exams.classify import classify, pick_subject, plain

        q = plain('A 3-week-old newborn with bilious vomiting; all of the following are true except')
        self.assertNotEqual(classify(q, '', ['Medical Students', 'Clinical', ''])[1], 'Myeloproliferative Diseases')
        self.assertEqual(classify(plain('Signs of pneumonia on chest x-ray'), '', ['SMLE - Prometric', 'SMLE - Medicine', '']),
                         ('Respiratory System', 'Pneumonia'))
        # A dental question never lands in a nursing or general medicine-only section.
        section, _ = classify(plain('Which material is used for a root canal filling?'), '', ['Dentistry', 'Residency Entrance - Dentistry', 'Endodontics'])
        self.assertIn(section, {'Clinical Dentistry', 'Dental Basic Sciences', 'Oral Biology and Pathology'})
        self.assertEqual(classify(plain('x + y = 7'), '', ['Residency Entrance - Medicine', 'MOH', 'Aptitude (IQ) - أسئلة القدرات'])[0], 'Aptitude (IQ)')
        medicine = ['Internal Medicine', 'Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Basic Sciences']
        self.assertEqual(pick_subject(plain('A 4-year-old child with fever'), 'Infectious Diseases', medicine), 'Pediatrics')
        self.assertEqual(pick_subject(plain('A 30-year-old pregnant woman'), 'Reproductive System', medicine), 'Obstetrics and Gynecology')
        self.assertEqual(pick_subject(plain('A 60-year-old man with chest pain'), 'Cardiovascular System', medicine), 'Internal Medicine')

    def test_command_fills_only_missing_links(self):
        from django.core.management import call_command
        from apps.content.models import ExamSection
        from apps.exams.models import ExamSectionLink

        call_command('seed_taxonomy', verbosity=0)
        root = Category.objects.get(name='SMLE - Prometric', parent=None)
        sub = root.children.get(name='SMLE - Medicine')
        q1 = Question.objects.create(text_question='<p>Pneumonia in a 70-year-old man</p>', category=root, sub_category=sub, status=1)
        q2 = Question.objects.create(text_question='<p>Hernia repair</p>', category=root, sub_category=sub, status=1)
        manual = ExamSection.objects.get(name='Hematology')
        ExamSectionLink.objects.create(question=q2, section=manual)
        call_command('classify_questions', verbosity=0)
        call_command('classify_questions', verbosity=0)
        self.assertEqual(list(q1.exam_section_links.values_list('section__name', flat=True)), ['Respiratory System'])
        self.assertEqual(list(q2.exam_section_links.values_list('section__name', flat=True)), ['Hematology'])  # kept
        q1.refresh_from_db()
        self.assertEqual(q1.sub_subcategory.name, 'Internal Medicine')


class LetterExplanationOrderTests(TestCase):
    def test_options_not_shuffled_when_explanation_names_a_letter(self):
        user = User.objects.create_user(phone='962791234503', password='pass')
        client = APIClient()
        client.force_authenticate(user)
        cat = Category.objects.create(name='C')
        q = Question.objects.create(text_question='q', category=cat, status=1, notes='<p>Correct Answer:</p><p>D. Fourth</p>')
        ids = [Answer.objects.create(question=q, answer_option=str(i)).id for i in range(6)]
        trail = ExamTrail.objects.create(user=user, title='t', shuffle_answers=True)
        trail.details.create(question=q)
        self.assertNotEqual(trail.answer_order(q.id, ids), ids)  # this trail would shuffle
        shown = client.get(f'/api/exams/{q.id}/get-question?exam_id={trail.id}').json()['data']['question']['answers']
        self.assertEqual([a['id'] for a in shown], ids)


class ExamResultTests(TestCase):
    def test_unanswered_questions_are_skipped_not_wrong_and_reports_use_real_questions(self):
        from apps.content.models import ExamSection
        from apps.exams.models import ExamSectionLink

        user = User.objects.create_user(phone='962791234504', password='pass')
        client = APIClient()
        client.force_authenticate(user)
        root = Category.objects.create(name='Board')
        peds = Category.objects.create(name='Pediatrics', parent=root, level=2)
        section = ExamSection.objects.create(name='Respiratory System')
        trail = ExamTrail.objects.create(user=user, title='t')
        for i in range(5):
            q = Question.objects.create(text_question=f'q{i}', category=root, sub_category=peds, status=1)
            right = Answer.objects.create(question=q, answer_option='r')
            wrong = Answer.objects.create(question=q, answer_option='w')
            ExamSectionLink.objects.create(question=q, section=section)
            # q0 right, q1 wrong, q2..q4 not answered
            answer = right if i == 0 else wrong if i == 1 else None
            trail.details.create(question=q, answer=answer, is_correct=(i == 0) if answer else None)
        trail.finish()
        self.assertEqual((trail.total_questions, trail.correct_answers, trail.wrong_answers), (5, 1, 1))

        data = client.get(f'/api/exams/{trail.id}/get').json()['data']
        subs = data['exam_report']['sub_categories']['result']
        self.assertEqual(subs, [{'id': peds.id, 'name': 'Pediatrics', 'total_questions': 5,
                                 'correct_answers': 1, 'wrong_answers': 1, 'skipped': 3}])
        self.assertEqual(data['exam_report']['sections']['result'][0]['name'], 'Respiratory System')
        self.assertIsNotNone(data['exam']['time_spent_minutes'])


class ExamAnalyticsTests(TestCase):
    """GET /exams/<id>/analytics: scoring, timing and access rules."""

    def setUp(self):
        self.user = User.objects.create_user(phone='962791234505', password='pass', first_name='Sara', last_name='Ali')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.root = Category.objects.create(name='Board')
        self.peds = Category.objects.create(name='Pediatrics', parent=self.root, level=2)
        subscribe(self.user, self.root)

    def make_trail(self, plan, mode='exam', status='completed', times=None):
        """plan: string of c (correct), w (wrong), u (unanswered)."""
        trail = ExamTrail.objects.create(user=self.user, title='Board', mode=mode)
        trail.categories.set([self.root])
        for i, kind in enumerate(plan):
            q = Question.objects.create(text_question=f'q{i}', category=self.root, sub_category=self.peds, status=1)
            right = Answer.objects.create(question=q, answer_option='r')
            wrong = Answer.objects.create(question=q, answer_option='w')
            q.correct_answer = right
            q.save()
            answer = {'c': right, 'w': wrong, 'u': None}[kind]
            trail.details.create(question=q, answer=answer, is_correct=(kind == 'c') if answer else None,
                                 time_spent_seconds=(times[i] if times else None))
        if status == 'completed':
            trail.finish()
        return trail

    def get(self, trail):
        return self.client.get(f'/api/exams/{trail.id}/analytics')

    def summary(self, plan):
        return self.get(self.make_trail(plan)).json()['data']['summary']

    def test_scoring_cases(self):
        none = self.summary('u' * 10)
        self.assertEqual((none['score'], none['accuracy'], none['wrong'], none['unanswered'], none['completion']), (0, None, 0, 10, 0))
        few = self.summary('cww' + 'u' * 44)  # 3 answered of 47
        self.assertEqual((few['correct'], few['wrong'], few['unanswered'], few['answered']), (1, 2, 44, 3))
        self.assertEqual((few['score'], few['accuracy'], few['completion']), (2.1, 33.3, 6.4))
        self.assertEqual(few['level'], 'needs_improvement')
        self.assertFalse(few['passed'])
        full = self.summary('c' * 10)
        self.assertEqual((full['score'], full['accuracy'], full['level'], full['passed']), (100, 100, 'excellent', True))
        zero = self.summary('w' * 5)
        self.assertEqual((zero['score'], zero['accuracy'], zero['wrong'], zero['unanswered']), (0, 0, 5, 0))

    def test_pass_mark_from_settings(self):
        from apps.content.models import Setting
        Setting.objects.create(key='exam_pass_mark', value='50')
        s = self.summary('ccww')
        self.assertEqual((s['score'], s['pass_mark'], s['passed'], s['level']), (50, 50, True, 'good'))

    def test_old_attempt_has_no_question_timing(self):
        time = self.get(self.make_trail('cwu')).json()['data']['time']
        self.assertFalse(time['has_question_timing'])
        self.assertIsNone(time['avg_answered_seconds'])
        self.assertIsNone(time['quadrants'])

    def test_question_timing_and_quadrants(self):
        data = self.get(self.make_trail('cwcu', times=[30, 200, 150, 10])).json()['data']
        time = data['time']
        self.assertTrue(time['has_question_timing'])
        self.assertEqual(time['target_seconds'], 90)
        self.assertEqual(time['quadrants'], {'fast_correct': 1, 'fast_wrong': 0, 'slow_correct': 1, 'slow_wrong': 1})
        self.assertEqual((time['fastest'], time['slowest']), ({'number': 1, 'seconds': 30}, {'number': 2, 'seconds': 200}))
        self.assertEqual(time['avg_answered_seconds'], 127)
        subject = data['breakdown']['subjects'][0]
        self.assertEqual((subject['name'], subject['correct'], subject['wrong'], subject['unanswered'], subject['accuracy']),
                         ('Pediatrics', 2, 1, 1, 66.7))

    def test_access_rules(self):
        running = self.make_trail('cw', status='in_progress')
        self.assertEqual(self.get(running).status_code, 409)  # exam mode: no results before submitting
        other = User.objects.create_user(phone='962791234506', password='pass')
        theirs = ExamTrail.objects.create(user=other, title='x', status='completed')
        self.assertEqual(self.get(theirs).status_code, 404)

    def test_attempts_of_the_same_exam(self):
        first = self.make_trail('cw')
        second = self.make_trail('cc')
        attempts = self.get(second).json()['data']['attempts']
        self.assertEqual([a['id'] for a in attempts], [first.id, second.id])
        self.assertEqual(self.get(second).json()['data']['exam']['attempt_number'], 2)

    def test_question_time_is_added_and_closed_after_submit(self):
        trail = self.make_trail('cw', status='in_progress')
        qid = trail.details.first().question_id
        trail.details.update(time_spent_seconds=None)
        for seconds in (40, 25):
            self.client.post(f'/api/exams/{trail.id}/question-time', {'question_id': qid, 'seconds': seconds}, format='json')
        self.assertEqual(trail.details.get(question_id=qid).time_spent_seconds, 65)
        trail.finish()
        res = self.client.post(f'/api/exams/{trail.id}/question-time', {'question_id': qid, 'seconds': 99}, format='json')
        self.assertFalse(res.json()['data']['recorded'])
        self.assertEqual(trail.details.get(question_id=qid).time_spent_seconds, 65)

    def test_retake_creates_a_new_attempt_with_the_same_filters(self):
        old = self.make_trail('cwu')
        res = self.client.post(f'/api/exams/{old.id}/retake', format='json')
        self.assertEqual(res.status_code, 200, res.json())
        new = ExamTrail.objects.get(pk=res.json()['data']['exam_id'])
        self.assertNotEqual(new.id, old.id)
        self.assertEqual(list(new.categories.values_list('id', flat=True)), [self.root.id])
        self.assertEqual(new.details.count(), 3)
        self.assertEqual(new.status, 'in_progress')
