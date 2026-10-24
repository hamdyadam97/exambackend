"""
Exam and question models.
"""
import random
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def exam_classification_q(prefix='', category_ids=None, sub_category_ids=None,
                          sub_sub_category_ids=None, section_ids=None, topic_ids=None):
    """Cumulative (AND) filter for the exam question pool, shared by the
    creation wizard counts and the actual exam build so both always agree.

    A question belongs to the pool when it is active and not deleted, and it
    must satisfy every classification level explicitly selected:
    specialty (category), category (sub_category), sub-category
    (sub_subcategory), section and topic. Levels left empty impose no
    restriction. `prefix` is the ORM path from the annotated model to
    Question (e.g. 'questions_as_sub', 'exam_section_links__question')."""
    p = f'{prefix}__' if prefix else ''
    chain = Q(**{f'{p}status': 1, f'{p}deleted_at__isnull': True})
    if category_ids:
        chain &= Q(**{f'{p}category_id__in': category_ids})
    if sub_category_ids:
        chain &= Q(**{f'{p}sub_category_id__in': sub_category_ids})
    if sub_sub_category_ids:
        chain &= Q(**{f'{p}sub_subcategory_id__in': sub_sub_category_ids})
    if section_ids:
        chain &= Q(**{f'{p}exam_section_links__section_id__in': section_ids})
    if topic_ids:
        chain &= Q(**{f'{p}question_topics__topic_id__in': topic_ids})
    return chain


class Question(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    QUESTION_TYPE_EMPTY = 0
    QUESTION_TYPE_QUESTION = 1
    QUESTION_TYPE_TEXT = 2
    QUESTION_TYPE_CHOICES = {
        QUESTION_TYPE_EMPTY: _('Empty'),
        QUESTION_TYPE_QUESTION: _('Question'),
        QUESTION_TYPE_TEXT: _('Text'),
    }

    ANSWER_TYPE_RADIO = 1
    ANSWER_TYPE_MULTIPLE = 2
    ANSWER_TYPE_CHOICES = {
        ANSWER_TYPE_RADIO: _('Radio'),
        ANSWER_TYPE_MULTIPLE: _('Multiple Choice'),
    }

    text_question = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    question_type = models.IntegerField(choices=list(QUESTION_TYPE_CHOICES.items()), null=True, blank=True)
    answer_type = models.IntegerField(choices=list(ANSWER_TYPE_CHOICES.items()), null=True, blank=True)
    hint = models.TextField(null=True, blank=True)
    show_answer_explanation = models.BooleanField(default=False)
    show_hint = models.BooleanField(default=False)
    show_answer = models.BooleanField(default=False)
    show_video = models.BooleanField(default=False)
    video_link = models.URLField(max_length=500, null=True, blank=True)
    time_minutes = models.PositiveIntegerField(null=True, blank=True)
    question_has_image = models.BooleanField(default=False)
    question_image = models.URLField(max_length=500, null=True, blank=True)
    answer_has_image = models.BooleanField(default=False)
    answer_image = models.URLField(max_length=500, null=True, blank=True)
    correct_answer = models.ForeignKey(
        'exams.Answer',
        on_delete=models.SET_NULL,
        db_column='correct_answer_id',
        related_name='is_correct_for',
        null=True,
        blank=True
    )
    category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='questions',
        null=True,
        blank=True
    )
    sub_category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_category_id',
        related_name='questions_as_sub',
        null=True,
        blank=True,
        limit_choices_to={'level': 2}
    )
    sub_subcategory = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_subcategory_id',
        related_name='questions_as_sub_sub',
        null=True,
        blank=True,
        limit_choices_to={'level': 3}
    )
    sort_order = models.IntegerField(default=0, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'questions'
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category', 'sub_category', 'sub_subcategory']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.text_question or f'Question {self.id}'

    @staticmethod
    def modes():
        return {
            'all': {'name': _('All'), 'desc': _('All questions')},
            'unused': {'name': _('Unused'), 'desc': _('Not used before')},
            'used': {'name': _('Used'), 'desc': _('Used before')},
            'correct': {'name': _('Correct'), 'desc': _('Answered correctly before')},
            'incorrect': {'name': _('Incorrect'), 'desc': _('Answered incorrectly before')},
            'marked': {'name': _('Marked'), 'desc': _('Marked questions')},
        }


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='answers'
    )
    answer_option = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'questions_answers'
        verbose_name = _('Answer')
        verbose_name_plural = _('Answers')
        indexes = [
            models.Index(fields=['question']),
        ]


class QuestionTopic(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='question_topics'
    )
    topic = models.ForeignKey(
        'content.QuestionsTopic',
        on_delete=models.CASCADE,
        db_column='topic_id',
        related_name='question_topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'question_topics'
        verbose_name = _('Question Topic')
        verbose_name_plural = _('Question Topics')
        unique_together = [('question', 'topic')]


class ExamSectionLink(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='exam_section_links'
    )
    section = models.ForeignKey(
        'content.ExamSection',
        on_delete=models.CASCADE,
        db_column='section_id',
        related_name='exam_section_links'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exam_sections'
        verbose_name = _('Exam Section Link')
        verbose_name_plural = _('Exam Section Links')
        unique_together = [('question', 'section')]


class Exam(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    DIFFICULTY_CHOICES = {
        BEGINNER: _('Beginner'),
        INTERMEDIATE: _('Intermediate'),
        ADVANCED: _('Advanced'),
    }

    EXAM_TYPE_MOCK = 'mock'
    EXAM_TYPE_PRACTICE = 'practice'
    EXAM_TYPE_FINAL = 'final'
    EXAM_TYPE_ASSESSMENT = 'assessment'
    EXAM_TYPE_CHOICES = {
        EXAM_TYPE_MOCK: _('Mock Exam'),
        EXAM_TYPE_PRACTICE: _('Practice Exam'),
        EXAM_TYPE_FINAL: _('Final Exam'),
        EXAM_TYPE_ASSESSMENT: _('Assessment'),
    }

    category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='cat_id',
        related_name='exams',
        null=True,
        blank=True
    )
    sub_category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_cat_id',
        related_name='exams_as_sub',
        null=True,
        blank=True,
        limit_choices_to={'level': 2}
    )
    sub_sub_category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_sub_cat_id',
        related_name='exams_as_sub_sub',
        null=True,
        blank=True,
        limit_choices_to={'level': 3}
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    icon = models.URLField(max_length=500, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    type = models.PositiveIntegerField(null=True, blank=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    order = models.PositiveIntegerField(default=0, null=True, blank=True)
    hint = models.TextField(null=True, blank=True)
    show_hint = models.BooleanField(default=False)
    show_answer = models.BooleanField(default=False)
    video_link = models.URLField(max_length=500, null=True, blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    difficulty_level = models.PositiveSmallIntegerField(
        choices=list(DIFFICULTY_CHOICES.items()),
        null=True,
        blank=True,
    )
    attempts_allowed = models.PositiveIntegerField(default=1)
    is_featured = models.BooleanField(default=False)
    language = models.CharField(max_length=50, null=True, blank=True)
    exam_type = models.CharField(max_length=50, choices=list(EXAM_TYPE_CHOICES.items()), null=True, blank=True)
    what_youll_be_tested_on = models.TextField(null=True, blank=True)
    skills_covered = models.TextField(null=True, blank=True)
    instructions = models.TextField(null=True, blank=True)
    requirements = models.TextField(null=True, blank=True)
    rules_policies = models.TextField(null=True, blank=True)
    has_instant_result = models.BooleanField(default=True)
    has_auto_save = models.BooleanField(default=True)
    has_timer = models.BooleanField(default=True)
    has_random_questions = models.BooleanField(default=True)
    has_progress_tracking = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'exams'
        verbose_name = _('Exam')
        verbose_name_plural = _('Exams')
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category', 'sub_category', 'sub_sub_category']),
        ]

    def __str__(self):
        return self.title or str(self.id)


class ExamQuestion(models.Model):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='exam_questions'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='exam_questions'
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'exam_questions'
        verbose_name = _('Exam Question')
        verbose_name_plural = _('Exam Questions')
        unique_together = [('exam', 'question')]
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['exam', 'order']),
        ]


class UserExam(models.Model):
    STATUS_NEW = 0
    STATUS_IN_PROGRESS = 1
    STATUS_SUBMITTED = 2
    STATUS_CHOICES = {
        STATUS_NEW: _('New'),
        STATUS_IN_PROGRESS: _('In Progress'),
        STATUS_SUBMITTED: _('Submitted'),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_exams'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='user_exams'
    )
    score = models.PositiveIntegerField(null=True, blank=True)
    correct_answers = models.PositiveIntegerField(default=0)
    wrong_answers = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_exams'
        verbose_name = _('User Exam')
        verbose_name_plural = _('User Exams')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'exam']),
        ]


class UserExamAnswer(models.Model):
    user_exam = models.ForeignKey(
        UserExam,
        on_delete=models.CASCADE,
        db_column='user_exam_id',
        related_name='answers',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_exam_answers'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='user_exam_answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='user_exam_answers'
    )
    answer = models.CharField(max_length=255, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_exam_questions_answers'
        verbose_name = _('User Exam Answer')
        verbose_name_plural = _('User Exam Answers')
        indexes = [
            models.Index(fields=['user_exam']),
            models.Index(fields=['user', 'exam']),
        ]


class UserExamTrial(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='user_exam_trials'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='user_exam_trials'
    )
    subscription = models.ForeignKey(
        'packages.UserPackage',
        on_delete=models.CASCADE,
        db_column='subscription_id',
        related_name='user_exam_trials',
        null=True,
        blank=True
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_exam_trials'
        verbose_name = _('User Exam Trial')
        verbose_name_plural = _('User Exam Trials')
        indexes = [
            models.Index(fields=['user', 'exam']),
        ]


class ExamTrail(models.Model):
    MODE_TUTOR = 'tatur'
    MODE_EXAM = 'exam'
    MODE_CHOICES = [
        (MODE_TUTOR, _('Tutor Mode')),
        (MODE_EXAM, _('Exam Mode')),
    ]

    QUESTION_MODE_ALL = 'all'
    QUESTION_MODE_UNUSED = 'unused'
    QUESTION_MODE_USED = 'used'
    QUESTION_MODE_CORRECT = 'correct'
    QUESTION_MODE_INCORRECT = 'incorrect'
    QUESTION_MODE_OMITTED = 'omitted'
    QUESTION_MODE_MARKED = 'marked'
    QUESTION_MODE_CHOICES = [
        (QUESTION_MODE_ALL, _('All')),
        (QUESTION_MODE_UNUSED, _('Unused')),
        (QUESTION_MODE_USED, _('Used')),
        (QUESTION_MODE_CORRECT, _('Correct')),
        (QUESTION_MODE_INCORRECT, _('Incorrect')),
        (QUESTION_MODE_OMITTED, _('Omitted')),
        (QUESTION_MODE_MARKED, _('Marked')),
    ]

    title = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='exam_trails'
    )
    question_count = models.PositiveIntegerField(default=0)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_TUTOR)
    is_timed_mode = models.BooleanField(default=False)
    question_mode = models.CharField(max_length=10, choices=QUESTION_MODE_CHOICES, default=QUESTION_MODE_ALL)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    wrong_answers = models.PositiveIntegerField(default=0)
    stages = models.JSONField(null=True, blank=True)
    current_stage = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=50, default='in_progress')
    # Set when the trail is an attempt at a ready-made Exam rather than a custom build.
    user_exam = models.ForeignKey(
        UserExam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trails'
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    categories = models.ManyToManyField(
        'content.Category',
        through='ExamTrailCategoryLink',
        related_name='exam_trails'
    )
    sub_categories = models.ManyToManyField(
        'content.Category',
        through='ExamTrailSubCategoryLink',
        related_name='exam_trails_as_sub'
    )
    sub_sub_categories = models.ManyToManyField(
        'content.Category',
        through='ExamTrailSubSubCategoryLink',
        related_name='exam_trails_as_sub_sub'
    )
    sections = models.ManyToManyField(
        'content.ExamSection',
        through='ExamTrailSectionLink',
        related_name='exam_trails'
    )
    topics = models.ManyToManyField(
        'content.QuestionsTopic',
        through='ExamTrailTopicLink',
        related_name='exam_trails'
    )
    questions = models.ManyToManyField(
        Question,
        through='ExamTrialDetail',
        related_name='exam_trails'
    )

    class Meta:
        db_table = 'exam_trails'
        verbose_name = _('Exam Trail')
        verbose_name_plural = _('Exam Trails')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.title

    def generate_stages(self, per_stage=40):
        remaining = self.question_count
        stages = []
        stage_num = 1
        while remaining > 0:
            count = min(remaining, per_stage)
            stages.append({'stage': stage_num, 'name': f'Stage {stage_num}', 'question_count': count})
            remaining -= count
            stage_num += 1
        self.stages = stages

    @staticmethod
    def get_exam_mode():
        return {'tatur': 'Tutor Mode', 'exam': 'Exam Mode'}

    def get_mode(self):
        return self.get_exam_mode().get(self.mode, '')

    def get_question_mode(self):
        return Question.modes().get(self.question_mode, {}).get('name', '')

    def get_question_query(self, sub_categories, sub_sub_categories, sections, topics):
        return Question.objects.filter(exam_classification_q(
            category_ids=list(self.categories.values_list('id', flat=True)),
            sub_category_ids=sub_categories,
            sub_sub_category_ids=sub_sub_categories,
            section_ids=sections,
            topic_ids=topics,
        )).distinct()

    def save_details(self):
        sub_categories = list(self.sub_categories.values_list('id', flat=True))
        sub_sub_categories = list(self.sub_sub_categories.values_list('id', flat=True))
        sections = list(self.sections.values_list('id', flat=True))

        topic_ids = list(self.topics.values_list('id', flat=True))
        explicit_topics = bool(topic_ids)
        if not topic_ids and sections:
            from apps.content.models import QuestionsTopic
            topic_ids = list(
                QuestionsTopic.objects.filter(
                    question_topics__question__exam_section_links__section_id__in=sections
                ).values_list('id', flat=True).distinct()
            )
            self.topics.set(topic_ids)

        # Only topics the user explicitly selected may narrow the pool.
        # Topics derived from sections only describe the selection for the
        # report and must not exclude questions without a topic link.
        filter_topics = topic_ids if explicit_topics else []

        if not self.question_count or self.question_count <= 0:
            self.question_count = self.get_question_query(sub_categories, sub_sub_categories, sections, filter_topics).values('id').distinct().count()

        questions = self.get_question_query(sub_categories, sub_sub_categories, sections, filter_topics)
        credential_questions = list(
            self.get_question_query(sub_categories, sub_sub_categories, sections, filter_topics)
            .values_list('id', flat=True).distinct()
        )

        if self.question_mode == self.QUESTION_MODE_ALL:
            pass
        elif self.question_mode == self.QUESTION_MODE_UNUSED:
            used = self._used_questions(credential_questions)
            questions = questions.exclude(id__in=used)
        elif self.question_mode == self.QUESTION_MODE_USED:
            used = self._used_questions(credential_questions)
            questions = questions.filter(id__in=used)
        elif self.question_mode == self.QUESTION_MODE_CORRECT:
            correct = self._correct_questions(credential_questions)
            questions = questions.filter(id__in=correct)
        elif self.question_mode == self.QUESTION_MODE_INCORRECT:
            incorrect = self._incorrect_questions(credential_questions)
            questions = questions.filter(id__in=incorrect)
        elif self.question_mode == self.QUESTION_MODE_MARKED:
            marked = self._marked_questions(credential_questions)
            questions = questions.filter(id__in=marked)

        question_ids = list(questions.order_by('?').values_list('id', flat=True).distinct()[:self.question_count])

        if not question_ids:
            raise ValueError('No questions found for selected criteria.')

        if self.question_count > len(question_ids):
            self.question_count = len(question_ids)

        self.generate_stages()
        self.current_stage = 1
        self.save()

        self.details.all().delete()
        details = [ExamTrialDetail(exam_trail=self, question_id=qid) for qid in question_ids]
        self.details.bulk_create(details)

    def _used_questions(self, credential_questions):
        return list(ExamTrialDetail.objects.filter(
            exam_trail__user=self.user,
            question_id__in=credential_questions,
        ).values_list('question_id', flat=True).distinct())

    def _correct_questions(self, credential_questions):
        return list(ExamTrialDetail.objects.filter(
            exam_trail__user=self.user,
            question_id__in=credential_questions,
            is_correct=True
        ).values_list('question_id', flat=True).distinct())

    def _incorrect_questions(self, credential_questions):
        return list(ExamTrialDetail.objects.filter(
            exam_trail__user=self.user,
            question_id__in=credential_questions,
            is_correct=False
        ).values_list('question_id', flat=True).distinct())

    def _marked_questions(self, credential_questions):
        return list(ExamTrialDetail.objects.filter(
            exam_trail__user=self.user,
            question_id__in=credential_questions,
            is_marked=True
        ).values_list('question_id', flat=True).distinct())

    # Answers sent this long after the deadline are still accepted, to absorb network latency.
    DEADLINE_GRACE_SECONDS = 15

    def reveals_answers(self):
        """Whether results may be shown: tutor mode shows them as you go, exam mode only after submitting."""
        return self.mode == self.MODE_TUTOR or self.status == 'completed'

    def reveals_question(self, question_id):
        """Whether the correct answer and explanation of one question may be shown."""
        if self.status == 'completed':
            return True
        return self.mode == self.MODE_TUTOR and self.details.filter(
            question_id=question_id, answer__isnull=False,
        ).exists()

    def grade(self, question_id, answer_id):
        """Grade an answer against the stored correct answer; None when the answer is cleared."""
        if answer_id is None:
            return None
        question = Question.objects.only('correct_answer_id').get(pk=question_id)
        return question.correct_answer_id == answer_id

    @property
    def deadline(self):
        if not self.duration_minutes or not self.created_at:
            return None
        return self.created_at + timedelta(minutes=self.duration_minutes)

    def remaining_seconds(self):
        """Seconds left before the deadline, or None for an untimed exam."""
        if self.deadline is None:
            return None
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    def is_expired(self):
        deadline = self.deadline
        return deadline is not None and timezone.now() > deadline + timedelta(seconds=self.DEADLINE_GRACE_SECONDS)

    def finish(self):
        """Close the trail, store its score, and record the attempt for ready-made exams."""
        total = self.details.count()
        correct = self.details.filter(is_correct=True).count()
        self.status = 'completed'
        self.total_questions = total
        self.correct_answers = correct
        self.wrong_answers = total - correct
        self.save()

        user_exam = self.user_exam
        if user_exam and user_exam.status != UserExam.STATUS_SUBMITTED:
            user_exam.status = UserExam.STATUS_SUBMITTED
            user_exam.correct_answers = correct
            user_exam.wrong_answers = total - correct
            user_exam.score = round(correct * 100 / total) if total else 0
            user_exam.end_date = timezone.now().date()
            user_exam.save()

    @classmethod
    def start_from_exam(cls, user, exam, user_exam):
        """Create a trail that replays a ready-made Exam's question list."""
        question_ids = list(
            exam.exam_questions.filter(
                deleted_at__isnull=True,
                question__status=Question.ACTIVE,
                question__deleted_at__isnull=True,
            ).order_by('order', 'id').values_list('question_id', flat=True)
        )
        if not question_ids:
            raise ValueError('This exam has no questions yet.')
        if exam.has_random_questions:
            random.shuffle(question_ids)

        trail = cls.objects.create(
            user=user,
            title=exam.title or 'Exam',
            mode=cls.MODE_EXAM,
            question_mode=cls.QUESTION_MODE_ALL,
            is_timed_mode=exam.has_timer,
            duration_minutes=exam.duration_minutes if exam.has_timer else None,
            question_count=len(question_ids),
            user_exam=user_exam,
        )
        if exam.category_id:
            trail.categories.set([exam.category_id])
        if exam.sub_category_id:
            trail.sub_categories.set([exam.sub_category_id])
        if exam.sub_sub_category_id:
            trail.sub_sub_categories.set([exam.sub_sub_category_id])
        trail.generate_stages()
        trail.save()
        # Details are read back ordered by id, so bulk_create keeps the exam's order.
        ExamTrialDetail.objects.bulk_create(
            [ExamTrialDetail(exam_trail=trail, question_id=qid) for qid in question_ids]
        )
        return trail

    def get_current_stage_questions(self):
        all_ids = list(self.details.order_by('id').values_list('question_id', flat=True))
        stages = self.stages or []
        current = self.current_stage or 1
        if not stages or len(stages) <= 1:
            return all_ids
        offset = sum(stages[i]['question_count'] for i in range(current - 1))
        count = stages[current - 1].get('question_count', 40)
        return all_ids[offset:offset + count]

    def get_stage_questions(self, stage_number):
        stages = self.stages or []
        all_ids = list(self.details.order_by('id').values_list('question_id', flat=True))
        if not stages or len(stages) <= 1 or stage_number < 1:
            return all_ids
        if stage_number > len(stages):
            return []
        offset = sum(stages[i]['question_count'] for i in range(stage_number - 1))
        count = stages[stage_number - 1].get('question_count', 40)
        return all_ids[offset:offset + count]

    def is_current_stage_complete(self):
        stage_qs = self.get_current_stage_questions()
        answered = self.details.filter(question_id__in=stage_qs, answer_id__isnull=False).count()
        return answered >= len(stage_qs)

    def advance_to_next_stage(self):
        stages = self.stages or []
        if not stages or len(stages) <= 1:
            return False
        current = self.current_stage or 1
        if current >= len(stages):
            return False
        self.current_stage = current + 1
        self.save(update_fields=['current_stage'])
        return True

    def get_category_report(self):
        result = []
        for category in self.categories.all():
            total = self.questions.filter(category=category).values_list('id', flat=True)
            total_ids = list(total)
            correct = self.details.filter(question_id__in=total_ids, is_correct=True).count() if total_ids else 0
            result.append({'id': category.id, 'name': category.name, 'total_questions': len(total_ids), 'correct_answers': correct})
        return {'title': 'Categories', 'result': result}

    def get_sub_category_report(self):
        result = []
        for sub in self.sub_categories.all():
            total = self.questions.filter(sub_category=sub).values_list('id', flat=True)
            total_ids = list(total)
            correct = self.details.filter(question_id__in=total_ids, is_correct=True).count() if total_ids else 0
            result.append({'id': sub.id, 'name': sub.name, 'total_questions': len(total_ids), 'correct_answers': correct})
        return {'title': 'Sub Categories', 'result': result}

    def get_sub_sub_category_report(self):
        result = []
        for sub in self.sub_sub_categories.all():
            total = self.questions.filter(sub_subcategory=sub).values_list('id', flat=True)
            total_ids = list(total)
            correct = self.details.filter(question_id__in=total_ids, is_correct=True).count() if total_ids else 0
            result.append({'id': sub.id, 'name': sub.name, 'total_questions': len(total_ids), 'correct_answers': correct})
        return {'title': 'Sub SubCategories', 'result': result}

    def get_section_report(self):
        result = []
        for section in self.sections.all():
            total = self.questions.filter(exam_section_links__section=section).values_list('id', flat=True)
            total_ids = list(total)
            correct = self.details.filter(question_id__in=total_ids, is_correct=True).count() if total_ids else 0
            result.append({'id': section.id, 'name': section.name, 'total_questions': len(total_ids), 'correct_answers': correct})
        return {'title': 'Sections', 'result': result}

    def get_topics_report(self):
        result = []
        for topic in self.topics.all():
            total = self.questions.filter(question_topics__topic=topic).values_list('id', flat=True)
            total_ids = list(total)
            correct = self.details.filter(question_id__in=total_ids, is_correct=True).count() if total_ids else 0
            result.append({'id': topic.id, 'name': topic.topic, 'total_questions': len(total_ids), 'correct_answers': correct})
        return {'title': 'Topics', 'result': result}


class ExamTrailCategoryLink(models.Model):
    category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='exam_trail_categories'
    )
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trail_id',
        related_name='exam_trail_categories'
    )

    class Meta:
        db_table = 'categories_exam_trails'
        unique_together = [('exam_trail', 'category')]


class ExamTrailSubCategoryLink(models.Model):
    sub_category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_category_id',
        related_name='exam_trail_sub_categories',
        limit_choices_to={'level': 2}
    )
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trail_id',
        related_name='exam_trail_sub_categories'
    )

    class Meta:
        db_table = 'sub_categories_exam_trails'
        unique_together = [('exam_trail', 'sub_category')]


class ExamTrailSubSubCategoryLink(models.Model):
    sub_sub_category = models.ForeignKey(
        'content.Category',
        on_delete=models.CASCADE,
        db_column='sub_sub_category_id',
        related_name='exam_trail_sub_sub_categories',
        limit_choices_to={'level': 3}
    )
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trail_id',
        related_name='exam_trail_sub_sub_categories'
    )

    class Meta:
        db_table = 'sub_sub_categories_exam_trails'
        unique_together = [('exam_trail', 'sub_sub_category')]


class ExamTrailSectionLink(models.Model):
    section = models.ForeignKey(
        'content.ExamSection',
        on_delete=models.CASCADE,
        db_column='section_id',
        related_name='exam_trail_sections'
    )
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trail_id',
        related_name='exam_trail_sections'
    )

    class Meta:
        db_table = 'exam_trails_sections'
        unique_together = [('exam_trail', 'section')]


class ExamTrailTopicLink(models.Model):
    topic = models.ForeignKey(
        'content.QuestionsTopic',
        on_delete=models.CASCADE,
        db_column='topic_id',
        related_name='exam_trail_topics'
    )
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trail_id',
        related_name='exam_trail_topics'
    )

    class Meta:
        db_table = 'exam_trails_topics'
        unique_together = [('exam_trail', 'topic')]


class ExamTrialDetail(models.Model):
    exam_trail = models.ForeignKey(
        ExamTrail,
        on_delete=models.CASCADE,
        db_column='exam_trial_id',
        related_name='details'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='trial_details'
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        db_column='answer_id',
        related_name='trial_details',
        null=True,
        blank=True
    )
    is_correct = models.BooleanField(null=True, blank=True)
    is_marked = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exam_trial_details'
        verbose_name = _('Exam Trial Detail')
        verbose_name_plural = _('Exam Trial Details')
        unique_together = [('exam_trail', 'question')]



