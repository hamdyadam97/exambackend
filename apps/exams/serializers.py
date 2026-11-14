"""
Exam and question serializers.
"""
from rest_framework import serializers
from apps.exams.models import (
    Question, Answer, QuestionTopic, ExamSectionLink,
    ExamTrail, ExamTrialDetail,
)
from apps.content.serializers import (
    CategoryResource, SectionResource, TopicResource, FaqResource,
)
from apps.core.utils import build_asset_url


class QuestionAnswerResource(serializers.ModelSerializer):
    answer = serializers.CharField(source='answer_option', read_only=True)

    class Meta:
        model = Answer
        fields = ['id', 'answer', 'created_at']


class QuestionResource(serializers.ModelSerializer):
    answer_type_str = serializers.SerializerMethodField()
    correct_answer_id = serializers.SerializerMethodField()
    show_hint = serializers.BooleanField(default=False)
    hint = serializers.CharField(allow_null=True)
    show_video = serializers.BooleanField(default=False)
    video_link = serializers.CharField(allow_null=True)
    question_has_image = serializers.BooleanField(default=False)
    question_image = serializers.SerializerMethodField()
    answer_has_image = serializers.BooleanField(default=False)
    answer_image = serializers.SerializerMethodField()
    show_answer = serializers.BooleanField(default=False)
    is_show_answer_explanation = serializers.BooleanField(source='show_answer_explanation', default=False)
    notes = serializers.CharField(allow_null=True)
    answers = QuestionAnswerResource(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'text_question', 'answer_type', 'answer_type_str', 'correct_answer_id',
            'show_hint', 'hint', 'show_video', 'video_link',
            'question_has_image', 'question_image', 'answer_has_image', 'answer_image',
            'show_answer', 'is_show_answer_explanation', 'notes', 'answers',
        ]

    # Hidden unless the view passes context={'reveal': True}, so answers never leak by default.
    ANSWER_FIELDS = ('correct_answer_id', 'notes', 'answer_image', 'is_show_answer_explanation', 'show_answer')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get('reveal'):
            for field in self.ANSWER_FIELDS:
                data[field] = None
        return data

    def get_answer_type_str(self, obj):
        return Question.ANSWER_TYPE_CHOICES.get(obj.answer_type, '')

    def get_correct_answer_id(self, obj):
        return obj.correct_answer_id if obj.correct_answer else None

    def get_question_image(self, obj):
        request = self.context.get('request')
        if obj.question_has_image and obj.question_image and request:
            return build_asset_url(request, 'question_images', obj.question_image)
        return None

    def get_answer_image(self, obj):
        request = self.context.get('request')
        if obj.answer_has_image and obj.answer_image and request:
            return build_asset_url(request, 'answer_images', obj.answer_image)
        return None


class ExamTrialDetailResource(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source='question.id', read_only=True)
    answer_id = serializers.IntegerField(source='answer.id', read_only=True, allow_null=True)

    class Meta:
        model = ExamTrialDetail
        fields = ['id', 'question_id', 'answer_id', 'is_correct', 'is_marked', 'is_review']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.exam_trail.reveals_answers():
            data['is_correct'] = None
        return data


def hide_scores(data, trail):
    """Blank out score fields of an exam-mode trail that has not been submitted yet."""
    if not trail.reveals_answers():
        for field in ('correct_answers', 'wrong_answers'):
            if field in data:
                data[field] = None
    return data


class ExamTrialResource(serializers.ModelSerializer):
    categories = CategoryResource(many=True, read_only=True)
    sub_categories = CategoryResource(many=True, read_only=True)
    sub_sub_categories = CategoryResource(many=True, read_only=True)
    sections = SectionResource(many=True, read_only=True)
    topics = TopicResource(many=True, read_only=True)
    mode_label = serializers.CharField(source='get_mode', read_only=True)
    question_mode_label = serializers.CharField(source='get_question_mode', read_only=True)
    time_spent_minutes = serializers.SerializerMethodField()

    class Meta:
        model = ExamTrail
        fields = [
            'id', 'title', 'mode', 'mode_label', 'question_mode', 'question_mode_label',
            'is_timed_mode', 'question_count', 'total_questions', 'correct_answers',
            'wrong_answers', 'stages', 'current_stage', 'status',
            'categories', 'sub_categories', 'sub_sub_categories', 'sections', 'topics',
            'duration_minutes', 'time_spent_minutes', 'created_at',
        ]

    def get_time_spent_minutes(self, obj):
        """From the start to the submission (the last save); never more than the time limit."""
        if obj.status != 'completed' or not obj.created_at or not obj.updated_at:
            return None
        minutes = max(1, round((obj.updated_at - obj.created_at).total_seconds() / 60))
        return min(minutes, obj.duration_minutes) if obj.duration_minutes else minutes


class CategoryNameResource(serializers.Serializer):
    """id and name only: exam lists never need a category's subtree."""
    id = serializers.IntegerField()
    name = serializers.CharField()


class ExamTrialIndexResource(serializers.ModelSerializer):
    categories = CategoryNameResource(many=True, read_only=True)
    details_count = serializers.IntegerField(read_only=True)
    path = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()

    class Meta:
        model = ExamTrail
        fields = [
            'id', 'title', 'mode', 'question_mode', 'question_count',
            'total_questions', 'correct_answers', 'wrong_answers',
            'status', 'current_stage', 'categories', 'details_count', 'created_at',
            'path', 'score',
        ]

    def get_path(self, obj):
        """[exam, specialty, subject] names the attempt was built from (first of each level)."""
        levels = (obj.categories.all(), obj.sub_categories.all(), obj.sub_sub_categories.all())
        return [items[0].name for items in levels if len(items)]

    def get_score(self, obj):
        """Correct / total x 100 for a submitted attempt, else None."""
        if obj.status != 'completed' or not obj.total_questions:
            return None
        return round((obj.correct_answers or 0) * 100 / obj.total_questions, 1)

    def to_representation(self, instance):
        return hide_scores(super().to_representation(instance), instance)


class ShowExamTrialResource(serializers.ModelSerializer):
    duration = serializers.IntegerField(source='duration_minutes', read_only=True)
    remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ExamTrail
        fields = [
            'id', 'title', 'mode', 'question_mode', 'is_timed_mode', 'duration', 'remaining_seconds',
            'question_count', 'total_questions', 'correct_answers',
            'wrong_answers', 'stages', 'current_stage', 'status',
        ]

    def get_remaining_seconds(self, obj):
        return obj.remaining_seconds()

    def to_representation(self, instance):
        return hide_scores(super().to_representation(instance), instance)


class ExamStoreSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    exam_mode = serializers.ChoiceField(choices=[('tatur', 'Tutor Mode'), ('exam', 'Exam Mode')], default='tatur')
    question_mode = serializers.ChoiceField(choices=[
        ('all', 'All'), ('unused', 'Unused'), ('used', 'Used'),
        ('correct', 'Correct'), ('incorrect', 'InCorrect'), ('marked', 'Marked'), ('saved', 'Saved'),
    ], default='all')
    is_timed_mode = serializers.BooleanField(default=False)
    duration_minutes = serializers.IntegerField(required=False, default=0, min_value=0, max_value=600)
    difficulty = serializers.ChoiceField(choices=['easy', 'medium', 'hard', 'mixed'], default='mixed')
    randomize_questions = serializers.BooleanField(default=True)
    randomize_answers = serializers.BooleanField(default=False)
    question_count = serializers.IntegerField(required=False, default=0)
    categories = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    sub_categories = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    sub_sub_categories = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    sections = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    topics = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class StoreQuestionAnswerSerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_null=True)),
        required=False,
        default=list,
    )


class StoreSingleQuestionAnswerSerializer(serializers.Serializer):
    # Correctness is graded on the server; any is_correct sent by the client is ignored.
    question_id = serializers.IntegerField()
    answer_id = serializers.IntegerField(allow_null=True)
    is_marked = serializers.BooleanField(required=False, default=False)
