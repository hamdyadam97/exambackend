"""
Tests for exams app.
"""
from django.test import TestCase
from apps.users.models import User
from apps.content.models import Category
from apps.exams.models import Question, Answer, Exam, ExamQuestion, ExamTrail
from apps.exams.services import ExamService, ExamTrailService


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
