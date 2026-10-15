from django import forms
from django.forms import inlineformset_factory
from apps.exams.models import Question, Answer, Exam, ExamQuestion
from apps.dashboard.forms import BaseDashboardForm


class QuestionForm(BaseDashboardForm):
    """Simplified question form for the dashboard."""

    class Meta:
        model = Question
        fields = [
            'text_question', 'category', 'sub_category', 'sub_subcategory',
            'answer_type', 'status', 'notes', 'hint',
            'show_answer_explanation', 'show_hint', 'show_answer', 'show_video',
            'video_link', 'time_minutes',
        ]


class AnswerForm(BaseDashboardForm):
    """Single answer form used in the inline formset."""

    is_correct = forms.BooleanField(
        label='الإجابة الصحيحة',
        required=False,
    )

    class Meta:
        model = Answer
        fields = ['answer_option', 'is_correct']


AnswerFormSet = inlineformset_factory(
    Question,
    Answer,
    form=AnswerForm,
    extra=4,
    can_delete=True,
    fields=['answer_option'],
)


class ExamForm(BaseDashboardForm):
    """Exam header form."""

    class Meta:
        model = Exam
        exclude = ['created_at', 'updated_at', 'deleted_at']


class ExamQuestionForm(BaseDashboardForm):
    """Inline exam-question form."""

    class Meta:
        model = ExamQuestion
        fields = ['question', 'order']


ExamQuestionFormSet = inlineformset_factory(
    Exam,
    ExamQuestion,
    form=ExamQuestionForm,
    extra=3,
    can_delete=True,
    fields=['question', 'order'],
)
