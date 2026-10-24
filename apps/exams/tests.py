"""
Tests for exams app.
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User
from apps.content.models import Category
from apps.exams.models import Question, Answer, Exam, ExamQuestion, ExamTrail, UserExam
from apps.exams.services import ExamService, ExamTrailService
from apps.packages.models import Package, UserPackage


class ExamServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.category = Category.objects.create(name='Test Category')
        self.exam = Exam.objects.create(title='Test Exam', category=self.category)
        self.question = Question.objects.create(
            text_question='What is 2+2?',
            category=self.category,
            answer_type=1,
        )
        self.correct = Answer.objects.create(question=self.question, answer_option='4')
        self.question.correct_answer = self.correct
        self.question.save()
        ExamQuestion.objects.create(exam=self.exam, question=self.question, order=1)

    def test_start_exam(self):
        user_exam = ExamService.start_exam(self.user, self.exam.id)
        self.assertEqual(user_exam.status, user_exam.STATUS_IN_PROGRESS)

    def test_submit_correct_answer(self):
        user_exam = ExamService.start_exam(self.user, self.exam.id)
        is_correct = ExamService.submit_answer(user_exam, self.question.id, str(self.correct.id))
        self.assertTrue(is_correct)

    def test_finish_exam(self):
        user_exam = ExamService.start_exam(self.user, self.exam.id)
        ExamService.submit_answer(user_exam, self.question.id, str(self.correct.id))
        user_exam = ExamService.finish_exam(user_exam)
        self.assertEqual(user_exam.status, user_exam.STATUS_SUBMITTED)
        self.assertEqual(user_exam.correct_answers, 1)


class ExamTrailServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.category = Category.objects.create(name='Test Category')
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


class ExamStartApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Nursing')
        self.exam = Exam.objects.create(
            title='Nursing Mock', category=self.category, status=Exam.ACTIVE,
            attempts_allowed=1, duration_minutes=30, has_random_questions=False,
        )
        self.questions = []
        for i in range(3):
            q = Question.objects.create(text_question=f'Q{i}', category=self.category, status=1)
            ExamQuestion.objects.create(exam=self.exam, question=q, order=i)
            self.questions.append(q)
        self.package = Package.objects.create(name='Nursing Package', category=self.category)

    def subscribe(self):
        UserPackage.objects.create(
            user=self.user, package=self.package,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
        )

    def start(self):
        return self.client.post(f'/api/exams/{self.exam.id}/start')

    def test_requires_subscription(self):
        res = self.start()
        self.assertEqual(res.status_code, 403)
        self.assertIn('SubscriptionRequired', res.json()['errors'])

    def test_expired_subscription_is_rejected(self):
        UserPackage.objects.create(
            user=self.user, package=self.package,
            end_date=timezone.now().date() - timedelta(days=1),
        )
        self.assertEqual(self.start().status_code, 403)

    def test_start_creates_trail_with_exam_questions_in_order(self):
        self.subscribe()
        res = self.start()
        self.assertEqual(res.status_code, 200)
        trail = ExamTrail.objects.get(pk=res.json()['data']['exam_id'])
        self.assertEqual(trail.mode, ExamTrail.MODE_EXAM)
        self.assertEqual(trail.duration_minutes, 30)
        self.assertEqual(
            list(trail.details.order_by('id').values_list('question_id', flat=True)),
            [q.id for q in self.questions],
        )
        self.assertEqual(trail.user_exam.status, UserExam.STATUS_IN_PROGRESS)

    def test_second_start_resumes_unfinished_attempt(self):
        self.subscribe()
        first = self.start().json()['data']['exam_id']
        res = self.start().json()['data']
        self.assertEqual(res['exam_id'], first)
        self.assertTrue(res['resumed'])
        self.assertEqual(UserExam.objects.filter(user=self.user, exam=self.exam).count(), 1)

    def test_finish_scores_attempt_and_enforces_attempt_limit(self):
        self.subscribe()
        trail_id = self.start().json()['data']['exam_id']
        trail = ExamTrail.objects.get(pk=trail_id)
        trail.details.filter(question=self.questions[0]).update(is_correct=True)
        self.assertEqual(self.client.post(f'/api/exams/{trail_id}/finish').status_code, 200)

        user_exam = UserExam.objects.get(user=self.user, exam=self.exam)
        self.assertEqual(user_exam.status, UserExam.STATUS_SUBMITTED)
        self.assertEqual(user_exam.score, 33)

        res = self.start()
        self.assertEqual(res.status_code, 403)
        self.assertIn('AttemptsExhausted', res.json()['errors'])

    def test_exam_without_questions(self):
        self.subscribe()
        ExamQuestion.objects.all().delete()
        self.assertEqual(self.start().status_code, 422)


class AnswerIntegrityTests(TestCase):
    """The correct answer must never reach the client early, and the client must not grade itself."""

    def setUp(self):
        from apps.exams.models import ExamTrialDetail

        self.user = User.objects.create_user(phone='962791234567', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        category = Category.objects.create(name='Surgery')
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


class ExamTimeLimitTests(ExamStartApiTests):
    """Reuses the start-exam fixture: a 30-minute exam with 3 questions and attempts_allowed=1."""

    def start_trail(self, minutes_ago=0):
        self.subscribe()
        trail_id = self.start().json()['data']['exam_id']
        ExamTrail.objects.filter(pk=trail_id).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
        return trail_id

    def answer(self, trail_id):
        return self.client.post(
            f'/api/exams/{trail_id}/store-single-question-answer',
            {'question_id': self.questions[0].id, 'answer_id': None, 'is_correct': True},
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
        self.assertEqual(UserExam.objects.get(user=self.user).status, UserExam.STATUS_SUBMITTED)

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

    def test_expired_attempt_is_not_resumed(self):
        self.exam.attempts_allowed = 2
        self.exam.save()
        expired_id = self.start_trail(minutes_ago=31)
        res = self.start().json()['data']
        self.assertNotEqual(res['exam_id'], expired_id)
        self.assertFalse(res['resumed'])

    def test_custom_exam_keeps_chosen_duration(self):
        res = self.client.post('/api/exams/store', {
            'exam_mode': 'exam', 'is_timed_mode': True, 'duration_minutes': 45,
            'question_count': 2, 'categories': [self.category.id],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(ExamTrail.objects.get(pk=res.json()['data']['exam_id']).duration_minutes, 45)


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
