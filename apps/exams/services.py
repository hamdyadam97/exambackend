"""
Exam domain services.
"""
from django.db import transaction
from django.db.models import Q
from apps.exams.models import ExamTrail, ExamTrialDetail, Question, UserExam, UserExamAnswer
from apps.users.services import AuditService


class ExamTrailService:
    """Handles creation and answering of exam trails."""

    @classmethod
    def create_trail(cls, user, data):
        with transaction.atomic():
            trail = ExamTrail.objects.create(
                user=user,
                title=data.get('title') or 'Exam',
                mode=data['exam_mode'],
                question_mode=data['question_mode'],
                is_timed_mode=data['is_timed_mode'],
                question_count=data['question_count'],
            )
            trail.categories.set(data['categories'])
            trail.sub_categories.set(data['sub_categories'])
            trail.sub_sub_categories.set(data['sub_sub_categories'])
            trail.sections.set(data['sections'])
            trail.save_details()
            return trail

    @classmethod
    def record_answer(cls, trail: ExamTrail, question_id: int, answer_id=None, is_correct=False, is_marked=False):
        detail, _ = ExamTrialDetail.objects.get_or_create(
            exam_trail=trail,
            question_id=question_id,
        )
        detail.answer_id = answer_id
        detail.is_correct = is_correct
        detail.is_marked = is_marked
        detail.save()
        cls._recalculate_stats(trail)
        return detail

    @classmethod
    def finish(cls, trail: ExamTrail):
        trail.status = 'completed'
        cls._recalculate_stats(trail)
        return trail

    @classmethod
    def _recalculate_stats(cls, trail: ExamTrail):
        total = trail.details.count()
        correct = trail.details.filter(is_correct=True).count()
        trail.total_questions = total
        trail.correct_answers = correct
        trail.wrong_answers = total - correct
        trail.save(update_fields=['total_questions', 'correct_answers', 'wrong_answers', 'status'])


class ExamService:
    """Handles regular exam attempts."""

    @classmethod
    def start_exam(cls, user, exam_id):
        user_exam, _ = UserExam.objects.get_or_create(
            user=user,
            exam_id=exam_id,
            defaults={'status': UserExam.STATUS_IN_PROGRESS},
        )
        return user_exam

    @classmethod
    def submit_answer(cls, user_exam: UserExam, question_id: int, answer_text: str):
        question = Question.objects.get(pk=question_id)
        correct_answer = question.correct_answer
        is_correct = correct_answer and str(correct_answer.id) == answer_text
        UserExamAnswer.objects.update_or_create(
            user_exam=user_exam,
            question_id=question_id,
            defaults={
                'user': user_exam.user,
                'exam': user_exam.exam,
                'answer': answer_text,
                'is_correct': is_correct,
            }
        )
        return is_correct

    @classmethod
    def finish_exam(cls, user_exam: UserExam):
        answers = user_exam.answers.all()
        correct = answers.filter(is_correct=True).count()
        total = answers.count()
        user_exam.correct_answers = correct
        user_exam.wrong_answers = total - correct
        user_exam.status = UserExam.STATUS_SUBMITTED
        user_exam.save()
        return user_exam
