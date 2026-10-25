"""
Exam and question serializers.
"""
from rest_framework import serializers
from apps.exams.models import (
    Question, Answer, QuestionTopic, ExamSectionLink,
    Exam, ExamQuestion, UserExam, UserExamAnswer,
    UserExamTrial, ExamTrail, ExamTrialDetail,
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


class ExamResource(serializers.ModelSerializer):
    category = CategoryResource(read_only=True)
    sub_category = CategoryResource(read_only=True)
    sub_sub_category = CategoryResource(read_only=True)
    questions_count = serializers.SerializerMethodField()
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'icon', 'duration_minutes', 'score',
            'difficulty_level', 'difficulty_label', 'attempts_allowed',
            'is_featured', 'status', 'order',
            'category', 'sub_category', 'sub_sub_category',
            'questions_count', 'created_at', 'updated_at',
        ]

    def get_questions_count(self, obj):
        return obj.exam_questions.filter(deleted_at__isnull=True).count()


class ExamDetailResource(serializers.ModelSerializer):
    category = CategoryResource(read_only=True)
    sub_category = CategoryResource(read_only=True)
    sub_sub_category = CategoryResource(read_only=True)
    questions_count = serializers.SerializerMethodField()
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    exam_type_label = serializers.CharField(source='get_exam_type_display', read_only=True)
    related_exams = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'icon', 'duration_minutes', 'score',
            'difficulty_level', 'difficulty_label', 'attempts_allowed',
            'is_featured', 'status', 'order',
            'language', 'exam_type', 'exam_type_label',
            'what_youll_be_tested_on', 'skills_covered', 'instructions',
            'requirements', 'rules_policies',
            'has_instant_result', 'has_auto_save', 'has_timer',
            'has_random_questions', 'has_progress_tracking', 'features',
            'category', 'sub_category', 'sub_sub_category',
            'questions_count', 'related_exams',
            'created_at', 'updated_at',
        ]

    def get_questions_count(self, obj):
        return obj.exam_questions.filter(deleted_at__isnull=True).count()

    def get_related_exams(self, obj):
        related = Exam.objects.filter(
            status=Exam.ACTIVE, deleted_at__isnull=True
        ).exclude(id=obj.id)
        if obj.category_id:
            related = related.filter(category_id=obj.category_id)
        return ExamResource(related.order_by('order', '-created_at')[:6], many=True, context=self.context).data

    def get_features(self, obj):
        return [
            {'key': 'instant_result', 'label': 'Instant result', 'enabled': obj.has_instant_result},
            {'key': 'auto_save', 'label': 'Auto save', 'enabled': obj.has_auto_save},
            {'key': 'timer', 'label': 'Timer', 'enabled': obj.has_timer},
            {'key': 'random_questions', 'label': 'Random questions', 'enabled': obj.has_random_questions},
            {'key': 'progress_tracking', 'label': 'Progress tracking', 'enabled': obj.has_progress_tracking},
        ]


class UserExamResource(serializers.ModelSerializer):
    class Meta:
        model = UserExam
        fields = '__all__'


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

    class Meta:
        model = ExamTrail
        fields = [
            'id', 'title', 'mode', 'mode_label', 'question_mode', 'question_mode_label',
            'is_timed_mode', 'question_count', 'total_questions', 'correct_answers',
            'wrong_answers', 'stages', 'current_stage', 'status',
            'categories', 'sub_categories', 'sub_sub_categories', 'sections', 'topics',
            'created_at',
        ]


class ExamTrialIndexResource(serializers.ModelSerializer):
    categories = CategoryResource(many=True, read_only=True)
    details_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExamTrail
        fields = [
            'id', 'title', 'mode', 'question_mode', 'question_count',
            'total_questions', 'correct_answers', 'wrong_answers',
            'status', 'current_stage', 'categories', 'details_count', 'created_at',
        ]

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
