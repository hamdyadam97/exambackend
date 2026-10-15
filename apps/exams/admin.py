from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from apps.core.admin_site import admin_site
from apps.exams.models import (
    Question, Answer, QuestionTopic, ExamSectionLink, Exam, ExamQuestion,
    UserExam, UserExamAnswer, UserExamTrial, ExamTrail, ExamTrialDetail,
    ExamTrailCategoryLink, ExamTrailSubCategoryLink, ExamTrailSubSubCategoryLink,
    ExamTrailSectionLink, ExamTrailTopicLink,
)


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1
    fields = ['answer_option']


class QuestionTopicInline(admin.TabularInline):
    model = QuestionTopic
    extra = 1
    autocomplete_fields = ['topic']


class ExamSectionLinkInline(admin.TabularInline):
    model = ExamSectionLink
    extra = 1
    autocomplete_fields = ['section']


class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'text_question_short', 'category', 'sub_category',
        'sub_subcategory', 'answer_type', 'answer_count',
        'topics_list', 'sections_list', 'status', 'created_at',
    ]
    list_filter = ['status', 'answer_type', 'category', 'created_at']
    search_fields = ['text_question', 'notes']
    inlines = [AnswerInline, QuestionTopicInline, ExamSectionLinkInline]
    autocomplete_fields = [
        'category', 'sub_category', 'sub_subcategory', 'correct_answer',
    ]
    list_select_related = ['category', 'sub_category', 'sub_subcategory']
    date_hierarchy = 'created_at'
    actions = ['activate', 'deactivate', 'duplicate_questions']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(answer_count=Count('answers'))

    @admin.display(description=_('Question'))
    def text_question_short(self, obj):
        return obj.text_question[:80] if obj.text_question else '-'

    @admin.display(description=_('Answers'))
    def answer_count(self, obj):
        return obj.answer_count

    @admin.display(description=_('Topics'))
    def topics_list(self, obj):
        return ', '.join(str(t.topic) for t in obj.question_topics.select_related('topic')[:5])

    @admin.display(description=_('Sections'))
    def sections_list(self, obj):
        return ', '.join(str(s.section) for s in obj.exam_section_links.select_related('section')[:5])

    @admin.action(description=_('Activate selected questions'))
    def activate(self, request, queryset):
        queryset.update(status=Question.ACTIVE)

    @admin.action(description=_('Deactivate selected questions'))
    def deactivate(self, request, queryset):
        queryset.update(status=Question.INACTIVE)

    @admin.action(description=_('Duplicate selected questions'))
    def duplicate_questions(self, request, queryset):
        for question in queryset.iterator():
            old_id = question.pk
            old_correct_id = question.correct_answer_id
            question.pk = None
            question.correct_answer = None
            question.save()

            answer_map = {}
            for answer in Answer.objects.filter(question_id=old_id):
                old_answer_id = answer.pk
                answer.pk = None
                answer.question = question
                answer.save()
                answer_map[old_answer_id] = answer.pk

            if old_correct_id and old_correct_id in answer_map:
                question.correct_answer_id = answer_map[old_correct_id]
                question.save(update_fields=['correct_answer_id'])

            for qt in QuestionTopic.objects.filter(question_id=old_id):
                QuestionTopic.objects.create(question=question, topic_id=qt.topic_id)

            for es in ExamSectionLink.objects.filter(question_id=old_id):
                ExamSectionLink.objects.create(question=question, section_id=es.section_id)



admin_site.register(Question, QuestionAdmin)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'answer_option_short', 'is_correct_for', 'created_at']
    search_fields = ['answer_option', 'question__text_question']
    autocomplete_fields = ['question']
    list_select_related = ['question']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    @admin.display(description=_('Answer'))
    def answer_option_short(self, obj):
        return obj.answer_option[:80] if obj.answer_option else '-'

    @admin.display(description=_('Correct?'), boolean=True)
    def is_correct_for(self, obj):
        return obj.is_correct_for.filter(id=obj.question_id).exists() if obj.question_id else False



admin_site.register(Answer, AnswerAdmin)
class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 1
    autocomplete_fields = ['question']


class ExamAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category', 'sub_category', 'sub_sub_category',
        'duration_minutes', 'question_count', 'difficulty_level',
        'attempts_allowed', 'certificate_available', 'is_featured',
        'exam_type', 'language', 'instructor', 'status', 'created_at',
    ]
    list_filter = ['status', 'difficulty_level', 'certificate_available', 'is_featured', 'exam_type', 'language', 'category', 'created_at']
    search_fields = ['title', 'description']
    inlines = [ExamQuestionInline]
    autocomplete_fields = ['category', 'sub_category', 'sub_sub_category', 'instructor']
    list_select_related = ['category', 'sub_category', 'sub_sub_category', 'instructor']
    date_hierarchy = 'created_at'
    actions = ['publish', 'unpublish', 'make_featured', 'remove_featured']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(question_count=Count('exam_questions'))

    @admin.display(description=_('Questions'))
    def question_count(self, obj):
        return obj.question_count

    @admin.action(description=_('Publish selected exams'))
    def publish(self, request, queryset):
        queryset.update(status=Exam.ACTIVE)

    @admin.action(description=_('Unpublish selected exams'))
    def unpublish(self, request, queryset):
        queryset.update(status=Exam.INACTIVE)

    @admin.action(description=_('Mark selected exams as featured'))
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description=_('Remove featured flag from selected exams'))
    def remove_featured(self, request, queryset):
        queryset.update(is_featured=False)



admin_site.register(Exam, ExamAdmin)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ['exam', 'question', 'order', 'created_at']
    list_filter = ['exam']
    search_fields = ['exam__title', 'question__text_question']
    autocomplete_fields = ['exam', 'question']
    list_editable = ['order']
    list_select_related = ['exam', 'question']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']



admin_site.register(ExamQuestion, ExamQuestionAdmin)
class UserExamAnswerInline(admin.TabularInline):
    model = UserExamAnswer
    extra = 0
    readonly_fields = ['user', 'exam', 'question', 'answer', 'is_correct', 'created_at']
    can_delete = False


class UserExamAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'exam', 'status', 'score',
        'correct_answers', 'wrong_answers', 'start_date', 'created_at',
    ]
    list_filter = ['status', 'created_at', 'start_date']
    search_fields = ['user__phone', 'exam__title']
    autocomplete_fields = ['user', 'exam']
    list_select_related = ['user', 'exam']
    inlines = [UserExamAnswerInline]
    date_hierarchy = 'created_at'
    actions = ['recalculate_scores']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    @admin.action(description=_('Recalculate scores for selected user exams'))
    def recalculate_scores(self, request, queryset):
        for user_exam in queryset:
            correct = user_exam.answers.filter(is_correct=True).count()
            wrong = user_exam.answers.filter(is_correct=False).count()
            user_exam.correct_answers = correct
            user_exam.wrong_answers = wrong
            user_exam.score = correct
            user_exam.save(update_fields=['correct_answers', 'wrong_answers', 'score'])



admin_site.register(UserExam, UserExamAdmin)
class UserExamAnswerAdmin(admin.ModelAdmin):
    list_display = ['user', 'exam', 'question', 'answer', 'is_correct', 'created_at']
    list_filter = ['is_correct', 'created_at']
    search_fields = ['user__phone', 'exam__title', 'question__text_question']
    autocomplete_fields = ['user', 'exam', 'question']
    list_select_related = ['user', 'exam', 'question']
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(UserExamAnswer, UserExamAnswerAdmin)
class UserExamTrialAdmin(admin.ModelAdmin):
    list_display = ['user', 'exam', 'date', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['user__phone', 'exam__title']
    autocomplete_fields = ['user', 'exam', 'subscription']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(UserExamTrial, UserExamTrialAdmin)
class ExamTrialDetailInline(admin.TabularInline):
    model = ExamTrialDetail
    extra = 0
    autocomplete_fields = ['question', 'answer']


class ExamTrailCategoryLinkInline(admin.TabularInline):
    model = ExamTrailCategoryLink
    extra = 0
    autocomplete_fields = ['category']


class ExamTrailSubCategoryLinkInline(admin.TabularInline):
    model = ExamTrailSubCategoryLink
    extra = 0
    autocomplete_fields = ['sub_category']


class ExamTrailSubSubCategoryLinkInline(admin.TabularInline):
    model = ExamTrailSubSubCategoryLink
    extra = 0
    autocomplete_fields = ['sub_sub_category']


class ExamTrailSectionLinkInline(admin.TabularInline):
    model = ExamTrailSectionLink
    extra = 0
    autocomplete_fields = ['section']


class ExamTrailTopicLinkInline(admin.TabularInline):
    model = ExamTrailTopicLink
    extra = 0
    autocomplete_fields = ['topic']


class ExamTrailAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'mode', 'question_mode', 'total_questions',
        'progress', 'status', 'created_at',
    ]
    list_filter = ['mode', 'question_mode', 'status', 'created_at']
    search_fields = ['title', 'user__phone']
    autocomplete_fields = ['user']
    list_select_related = ['user']
    inlines = [
        ExamTrailCategoryLinkInline, ExamTrailSubCategoryLinkInline,
        ExamTrailSubSubCategoryLinkInline, ExamTrailSectionLinkInline,
        ExamTrailTopicLinkInline, ExamTrialDetailInline,
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']

    @admin.display(description=_('Progress'))
    def progress(self, obj):
        total = obj.total_questions or 0
        correct = obj.correct_answers or 0
        if not total:
            return '-'
        return f"{correct}/{total} ({round(100 * correct / total)}%)"



admin_site.register(ExamTrail, ExamTrailAdmin)
class ExamTrialDetailAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'question', 'answer', 'is_correct', 'is_marked', 'created_at']
    list_filter = ['is_correct', 'is_marked', 'created_at']
    search_fields = ['exam_trail__title', 'question__text_question']
    autocomplete_fields = ['exam_trail', 'question', 'answer']
    list_select_related = ['exam_trail', 'question', 'answer']
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(ExamTrialDetail, ExamTrialDetailAdmin)
class ExamTrailCategoryLinkAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'category']
    search_fields = ['exam_trail__title', 'category__name']
    autocomplete_fields = ['exam_trail', 'category']
    list_select_related = ['exam_trail', 'category']



admin_site.register(ExamTrailCategoryLink, ExamTrailCategoryLinkAdmin)
class ExamTrailSubCategoryLinkAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'sub_category']
    search_fields = ['exam_trail__title', 'sub_category__name']
    autocomplete_fields = ['exam_trail', 'sub_category']
    list_select_related = ['exam_trail', 'sub_category']



admin_site.register(ExamTrailSubCategoryLink, ExamTrailSubCategoryLinkAdmin)
class ExamTrailSubSubCategoryLinkAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'sub_sub_category']
    search_fields = ['exam_trail__title', 'sub_sub_category__name']
    autocomplete_fields = ['exam_trail', 'sub_sub_category']
    list_select_related = ['exam_trail', 'sub_sub_category']



admin_site.register(ExamTrailSubSubCategoryLink, ExamTrailSubSubCategoryLinkAdmin)
class ExamTrailSectionLinkAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'section']
    search_fields = ['exam_trail__title', 'section__name']
    autocomplete_fields = ['exam_trail', 'section']
    list_select_related = ['exam_trail', 'section']



admin_site.register(ExamTrailSectionLink, ExamTrailSectionLinkAdmin)
class ExamTrailTopicLinkAdmin(admin.ModelAdmin):
    list_display = ['exam_trail', 'topic']
    search_fields = ['exam_trail__title', 'topic__topic']
    autocomplete_fields = ['exam_trail', 'topic']
    list_select_related = ['exam_trail', 'topic']

admin_site.register(ExamTrailTopicLink, ExamTrailTopicLinkAdmin)
