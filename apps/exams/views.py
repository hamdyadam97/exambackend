"""
Exam API views.
"""
import re

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Avg, Case, Count, ExpressionWrapper, F, FloatField, Max, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils.html import strip_tags
from django.utils.text import Truncator
from apps.exams.models import (
    Question, Answer, ExamTrail, ExamTrialDetail, SavedQuestion, exam_classification_q,
)
from apps.exams.serializers import (
    QuestionResource, ExamTrialResource, ExamTrialIndexResource,
    ExamTrialDetailResource, ShowExamTrialResource, ExamStoreSerializer,
    StoreQuestionAnswerSerializer, StoreSingleQuestionAnswerSerializer,
)
from apps.content.models import Category, ExamSection, QuestionsTopic
from apps.content.serializers import (
    CategoryResource, SectionResource, TopicResource,
)
from apps.core.utils import api_response, send_response, send_error, api_get, api_post
from apps.content.models import Setting
from apps.exams.insights import student_insights
from apps.packages.access import access_scope


LETTER_REFERENCE = re.compile(
    r'(correct\s+answer|answer\s+is|answer\s*:|option)\s*(is)?\s*[:\-]?\s*\(?[A-Ea-e]\s*[\).:]', re.I)


def scoped_q(request, *args, **kwargs):
    """exam_classification_q limited to what the requesting user's subscriptions open."""
    if not hasattr(request, '_access_scope'):
        request._access_scope = access_scope(request.user)
    return exam_classification_q(*args, scope=request._access_scope, **kwargs)


class BaseApiView(APIView):
    pass


def difficulty_param(request):
    """The builder's ?difficulty=easy|medium|hard as a Question difficulty, or None for mixed."""
    return Question.DIFFICULTY_BY_NAME.get(request.query_params.get('difficulty', ''))


def reject_if_closed(trail):
    """Error response when a trail no longer accepts answers; a timed-out trail is finished on the spot."""
    if trail.status == 'completed':
        return send_error('Exam already finished', {'ExamFinished': ['This exam has already been submitted']}, 409)
    if trail.is_expired():
        trail.finish()
        return send_error('Time is up', {'TimeUp': ['The time for this exam has ended']}, 409)
    return None


class StudentInsightsView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('StudentInsights')
    def get(self, request):
        return api_response(True, 'Fetched Successfully', student_insights(request.user))


class ExamQuestionStateView(BaseApiView):
    """Flag a question or mark it for later review inside an exam, without touching its answer."""
    permission_classes = [IsAuthenticated]

    @api_post('ExamQuestionState')
    def post(self, request, exam_id):
        detail = ExamTrialDetail.objects.filter(
            exam_trail_id=exam_id, exam_trail__user=request.user,
            question_id=request.data.get('question_id') or 0,
        ).first()
        if not detail:
            return send_error('Question not found', {'QuestionNotFound': ['This question is not part of this exam']})
        fields = [f for f in ('is_marked', 'is_review') if f in request.data]
        for field in fields:
            setattr(detail, field, request.data[field] in (True, 'true', 1, '1'))
        if fields:
            detail.save(update_fields=fields + ['updated_at'])
        return api_response(True, 'Saved', {
            'question_id': detail.question_id, 'is_marked': bool(detail.is_marked), 'is_review': detail.is_review,
        })


class SavedQuestionView(BaseApiView):
    """Bookmark (POST) or un-bookmark (DELETE) a question the student has met in one of their exams."""
    permission_classes = [IsAuthenticated]

    @api_post('SaveQuestion')
    def post(self, request, question_id):
        if not ExamTrialDetail.objects.filter(exam_trail__user=request.user, question_id=question_id).exists():
            return send_error('Question not found', {'QuestionNotFound': ['You can only save questions from your exams']})
        SavedQuestion.objects.get_or_create(user=request.user, question_id=question_id)
        return api_response(True, 'Saved', {'question_id': question_id, 'saved': True})

    def delete(self, request, question_id):
        SavedQuestion.objects.filter(user=request.user, question_id=question_id).delete()
        return api_response(True, 'Removed', {'question_id': question_id, 'saved': False})


class QuestionCollectionView(BaseApiView):
    """The student's saved, wrong or flagged questions, newest first."""
    permission_classes = [IsAuthenticated]
    LIMIT = 200

    @api_get('QuestionCollection')
    def get(self, request, kind):
        user = request.user
        if kind == 'saved':
            rows = SavedQuestion.objects.filter(user=user).values('question_id', 'created_at')
            dates = {r['question_id']: r['created_at'] for r in rows}
            counts = {}
        elif kind == 'wrong':
            rows = (
                ExamTrialDetail.graded_for(user).filter(is_correct=False)
                .values('question_id').annotate(times=Count('id'), last=Max('updated_at'))
            )
            dates = {r['question_id']: r['last'] for r in rows}
            counts = {r['question_id']: r['times'] for r in rows}
        elif kind == 'flagged':
            rows = (
                ExamTrialDetail.objects.filter(exam_trail__user=user, is_marked=True)
                .values('question_id').annotate(last=Max('updated_at'))
            )
            dates = {r['question_id']: r['last'] for r in rows}
            counts = {}
        else:
            return send_error('Not found', {'kind': ['Use saved, wrong or flagged']})

        ids = sorted(dates, key=lambda qid: dates[qid], reverse=True)[:self.LIMIT]
        saved_ids = set(SavedQuestion.objects.filter(user=user, question_id__in=ids).values_list('question_id', flat=True))
        questions = Question.objects.in_bulk(ids)
        items = []
        for qid in ids:
            question = questions.get(qid)
            if not question:
                continue
            items.append({
                'id': qid,
                'text': Truncator(strip_tags(question.text_question or '')).chars(220),
                'category': question.category.name if question.category_id else None,
                'category_id': question.category_id,
                'date': dates[qid],
                'times_wrong': counts.get(qid),
                'saved': qid in saved_ids,
            })
        return api_response(True, 'Fetched Successfully', {'questions': items, 'total': len(dates)})


class ExamListView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamList')
    def get(self, request):
        from apps.exams.analytics import _int_setting

        pass_mark = _int_setting('exam_pass_mark', 60)
        mine = ExamTrail.objects.filter(user=request.user)
        # Score of a submitted attempt, for the result filter and the score ordering.
        score = Case(
            When(status='completed', total_questions__gt=0,
                 then=ExpressionWrapper(F('correct_answers') * 100.0 / F('total_questions'), output_field=FloatField())),
            default=None, output_field=FloatField(),
        )
        exams = mine.prefetch_related('categories', 'sub_categories', 'sub_sub_categories').annotate(
            details_count=Count('details', filter=Q(details__answer_id__isnull=False)),
            score_value=score,
        )

        # Optional filters, all backward compatible: without them the list is what it always was.
        status = request.query_params.get('status')
        if status == 'completed':
            exams = exams.filter(status='completed')
        elif status == 'in_progress':
            exams = exams.exclude(status='completed')
        elif status == 'passed':
            exams = exams.filter(score_value__gte=pass_mark)
        elif status == 'failed':
            exams = exams.filter(status='completed', score_value__lt=pass_mark)
        query = (request.query_params.get('q') or '').strip()
        if query:
            ids = ExamTrail.objects.filter(user=request.user).filter(
                Q(title__icontains=query) | Q(categories__name__icontains=query)
                | Q(sub_categories__name__icontains=query) | Q(sub_sub_categories__name__icontains=query)
            ).values('id')
            exams = exams.filter(id__in=ids)
        ordering = {
            'date': ('created_at', 'id'),
            '-date': ('-created_at', '-id'),
            'score': (F('score_value').asc(nulls_last=True), '-created_at'),
            '-score': (F('score_value').desc(nulls_last=True), '-created_at'),
        }.get(request.query_params.get('ordering'), ('-created_at', '-id'))
        exams = exams.order_by(*ordering)

        from apps.core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(exams, request)

        completed = mine.filter(status='completed', total_questions__gt=0).annotate(score_value=score)
        average = completed.aggregate(avg=Avg('score_value'))['avg']
        data = {
            'exams': ExamTrialIndexResource(page, many=True, context={'request': request}).data,
            'pagination': {
                'count': paginator.page.paginator.count,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
            # Totals over all the attempts of the student, whatever filter is applied.
            'stats': {
                'total': mine.count(),
                'in_progress': mine.exclude(status='completed').count(),
                'completed': mine.filter(status='completed').count(),
                'passed': completed.filter(score_value__gte=pass_mark).count(),
                'average_score': round(average, 1) if average is not None else None,
            },
            'pass_mark': pass_mark,
        }
        return api_response(True, 'Fetched Successfully', data)


class ExamDetailView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamDetail')
    def get(self, request, exam_id):
        try:
            exam = ExamTrail.objects.prefetch_related(
                'categories', 'sub_categories', 'sections', 'topics'
            ).get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        if not exam.reveals_answers():
            return send_error(
                'Exam in progress',
                {'ExamInProgress': ['Results are available after the exam is submitted']},
                409,
            )

        data = {
            'exam': ExamTrialResource(exam, context={'request': request}).data,
            'exam_report': {
                'categories': exam.get_category_report(),
                'sub_categories': exam.get_sub_category_report(),
                'sub_sub_categories': exam.get_sub_sub_category_report(),
                'sections': exam.get_section_report(),
                'topics': exam.get_topics_report(),
            }
        }
        return api_response(True, 'Fetched Successfully', data)


class ExamCreateView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamCreate')
    def get(self, request):
        scope = access_scope(request.user)
        request._access_scope = scope
        roots = Category.objects.filter(level=Category.LEVEL_CATEGORY, parent=None, status=1)
        if not scope.everything:
            # The level-1 category above every subscription, whatever level the package is linked to.
            roots = roots.filter(id__in=scope.visible)
        categories = roots.annotate(
            questions_count=Count('questions', filter=scoped_q(request, 'questions'), distinct=True)
        ).order_by('name')

        return api_response(True, 'Fetched Successfully', {
            'exam_modes': ExamTrail.get_exam_mode(),
            'question_modes': Question.modes(),
            'questions_per_stage': 40,
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
        })


class ExamSubCategoriesView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamSubCategories')
    def get(self, request):
        category_ids = request.query_params.getlist('category_ids[]', [])
        if not category_ids:
            return api_response(True, 'Fetched Successfully', {'sub_categories': []})
        try:
            category_ids = [int(x) for x in category_ids]
        except ValueError:
            return api_response(True, 'Fetched Successfully', {'sub_categories': []})

        # The question must belong to one of the selected specialties (its
        # category FK) on top of carrying this category as its sub_category,
        # so the count is scoped to the specialty selection above it.
        chain = scoped_q(request, 'questions_as_sub', category_ids=category_ids)
        sub_categories = Category.objects.filter(
            parent_id__in=category_ids, status=1, level=Category.LEVEL_SUB_CATEGORY
        ).filter(chain).annotate(
            questions_count=Count('questions_as_sub', filter=chain, distinct=True)
        ).order_by('name').distinct()

        return api_response(True, 'Fetched Successfully', {
            'sub_categories': CategoryResource(sub_categories, many=True, context={'request': request}).data,
        })


class ExamSubSubCategoriesView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamSubSubCategories')
    def get(self, request):
        sub_category_ids = request.query_params.getlist('sub_category_ids[]', [])
        if not sub_category_ids:
            return api_response(True, 'Fetched Successfully', {'sub_sub_categories': []})
        try:
            sub_category_ids = [int(x) for x in sub_category_ids]
        except ValueError:
            return api_response(True, 'Fetched Successfully', {'sub_sub_categories': []})

        # Resolve the specialty roots of the selected categories so the count
        # is cumulative: specialty (via the question's category FK) AND
        # category (via its sub_category FK) AND this sub-category.
        spec_ids = list(Category.objects.filter(
            id__in=Category.objects.filter(id__in=sub_category_ids).values('parent_id')
        ).values_list('id', flat=True))

        chain = scoped_q(request, 
            'questions_as_sub_sub',
            category_ids=spec_ids,
            sub_category_ids=sub_category_ids,
        )
        sub_sub = Category.objects.filter(
            parent_id__in=sub_category_ids, status=1, level=Category.LEVEL_SUB_SUB_CATEGORY
        ).filter(chain).annotate(
            questions_count=Count('questions_as_sub_sub', filter=chain, distinct=True)
        ).order_by('name').distinct()

        return api_response(True, 'Fetched Successfully', {
            'sub_sub_categories': CategoryResource(sub_sub, many=True, context={'request': request}).data,
        })


class ExamSectionsView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamSections')
    def get(self, request):
        category_ids = request.query_params.getlist('category_ids[]', [])
        sub_category_ids = request.query_params.getlist('sub_category_ids[]', [])
        sub_sub_category_ids = request.query_params.getlist('sub_sub_category_ids[]', [])

        if not category_ids:
            return api_response(True, 'Fetched Successfully', {'sections': [], 'total_questions': 0, 'total_stages': 0})

        try:
            category_ids = [int(x) for x in category_ids]
            sub_category_ids = [int(x) for x in sub_category_ids] if sub_category_ids else []
            sub_sub_category_ids = [int(x) for x in sub_sub_category_ids] if sub_sub_category_ids else []
        except ValueError:
            return api_response(True, 'Fetched Successfully', {'sections': [], 'total_questions': 0, 'total_stages': 0})

        # Sections may be attached to any level of the selected category tree, or be shared by
        # every exam (no category: Respiratory System, Cardiovascular System, ...). Only sections
        # with questions on the selected path are listed (question_chain below).
        selected_category_ids = set(category_ids + sub_category_ids + sub_sub_category_ids)
        sections = ExamSection.objects.filter(Q(category_id__in=selected_category_ids) | Q(category__isnull=True))

        # The section count is cumulative: every classification level selected
        # above the section must match, plus a link to this section — the same
        # chain ExamTrail.get_question_query builds when drawing questions.
        difficulty = difficulty_param(request)
        question_chain = scoped_q(request, 
            'exam_section_links__question',
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
            difficulty=difficulty,
        )

        sections = sections.filter(question_chain).annotate(
            questions_count=Count('exam_section_links__question', filter=question_chain, distinct=True)
        ).order_by('name').distinct()

        # Total of the distinct questions available across all listed sections,
        # i.e. what the exam would draw if every listed section were selected.
        section_ids = list(sections.values_list('id', flat=True))
        total_filter = scoped_q(request, 
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
            section_ids=section_ids,
            difficulty=difficulty,
        )
        if not section_ids:
            # No question on this path is filed under a section yet: the student skips the section
            # step and the exam draws from the whole path.
            total_filter = scoped_q(request, 
                category_ids=category_ids,
                sub_category_ids=sub_category_ids,
                sub_sub_category_ids=sub_sub_category_ids,
                difficulty=difficulty,
            )
        total = Question.objects.filter(total_filter).distinct().count()

        return api_response(True, 'Fetched Successfully', {
            'sections': SectionResource(sections, many=True, context={'request': request}).data,
            'total_questions': total,
            'total_stages': (total + 39) // 40 if total > 0 else 0,
        })


class ExamTopicsView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamTopics')
    def get(self, request):
        section_ids = request.query_params.getlist('section_ids[]', [])
        if not section_ids:
            return api_response(True, 'Fetched Successfully', {'topics': []})
        try:
            section_ids = [int(x) for x in section_ids]
        except ValueError:
            return api_response(True, 'Fetched Successfully', {'topics': []})

        category_ids = request.query_params.getlist('category_ids[]', [])
        sub_category_ids = request.query_params.getlist('sub_category_ids[]', [])
        sub_sub_category_ids = request.query_params.getlist('sub_sub_category_ids[]', [])
        try:
            category_ids = [int(x) for x in category_ids] if category_ids else []
            sub_category_ids = [int(x) for x in sub_category_ids] if sub_category_ids else []
            sub_sub_category_ids = [int(x) for x in sub_sub_category_ids] if sub_sub_category_ids else []
        except ValueError:
            category_ids, sub_category_ids, sub_sub_category_ids = [], [], []

        # Same cumulative chain as the sections step, plus the selected
        # sections, so a topic only counts questions matching the whole
        # classification path above it.
        question_chain = scoped_q(request, 
            'question_topics__question',
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
            section_ids=section_ids,
            difficulty=difficulty_param(request),
        )

        topics = QuestionsTopic.objects.filter(question_chain).annotate(
            questions_count=Count('question_topics__question', filter=question_chain, distinct=True)
        ).order_by('topic').distinct()

        return api_response(True, 'Fetched Successfully', {
            'topics': TopicResource(topics, many=True, context={'request': request}).data,
        })


class ExamRefreshView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamRefresh')
    def get(self, request):
        category_ids = request.query_params.getlist('category_ids[]', [])
        sub_category_ids = request.query_params.getlist('sub_category_ids[]', [])
        sub_sub_category_ids = request.query_params.getlist('sub_sub_category_ids[]', [])
        section_ids = request.query_params.getlist('section_ids[]', [])

        data = {'questions_per_stage': 40}

        cids, scids, sscids = [], [], []
        if category_ids:
            try:
                cids = [int(x) for x in category_ids]
            except ValueError:
                cids = []
        if sub_category_ids:
            try:
                scids = [int(x) for x in sub_category_ids]
            except ValueError:
                scids = []
        if sub_sub_category_ids:
            try:
                sscids = [int(x) for x in sub_sub_category_ids]
            except ValueError:
                sscids = []

        if cids:
            chain = scoped_q(request, 'questions_as_sub', category_ids=cids)
            subs = Category.objects.filter(
                parent_id__in=cids, status=1, level=Category.LEVEL_SUB_CATEGORY
            ).filter(chain).annotate(
                questions_count=Count('questions_as_sub', filter=chain, distinct=True)
            ).order_by('name').distinct()
            data['sub_categories'] = CategoryResource(subs, many=True, context={'request': request}).data

        if scids:
            rspec_ids = list(Category.objects.filter(
                id__in=Category.objects.filter(id__in=scids).values('parent_id')
            ).values_list('id', flat=True))
            rchain = scoped_q(request, 
                'questions_as_sub_sub',
                category_ids=rspec_ids,
                sub_category_ids=scids,
            )
            ssubs = Category.objects.filter(
                parent_id__in=scids, status=1, level=Category.LEVEL_SUB_SUB_CATEGORY
            ).filter(rchain).annotate(
                questions_count=Count('questions_as_sub_sub', filter=rchain, distinct=True)
            ).order_by('name').distinct()
            data['sub_sub_categories'] = CategoryResource(ssubs, many=True, context={'request': request}).data

        if cids:
            selected_category_ids = set(cids + scids + sscids)
            sections = ExamSection.objects.filter(Q(category_id__in=selected_category_ids) | Q(category__isnull=True))

            question_chain = scoped_q(request, 
                'exam_section_links__question',
                category_ids=cids,
                sub_category_ids=scids,
                sub_sub_category_ids=sscids,
            )

            sections = sections.filter(question_chain).annotate(
                questions_count=Count('exam_section_links__question', filter=question_chain, distinct=True)
            ).order_by('name').distinct()
            data['sections'] = SectionResource(sections, many=True, context={'request': request}).data

            sids_for_total = list(sections.values_list('id', flat=True))
            total_filter = scoped_q(request, 
                category_ids=cids,
                sub_category_ids=scids,
                sub_sub_category_ids=sscids,
                section_ids=sids_for_total,
            )
            if not sids_for_total:
                total_filter = scoped_q(request, category_ids=cids, sub_category_ids=scids, sub_sub_category_ids=sscids)
            total = Question.objects.filter(total_filter).distinct().count()
            data['total_questions'] = total
            data['total_stages'] = (total + 39) // 40 if total > 0 else 0

        if section_ids:
            try:
                sids = [int(x) for x in section_ids]
            except ValueError:
                sids = []
            question_chain = scoped_q(request, 
                'question_topics__question',
                category_ids=cids,
                sub_category_ids=scids,
                sub_sub_category_ids=sscids,
                section_ids=sids,
            )
            topics = QuestionsTopic.objects.filter(question_chain).annotate(
                questions_count=Count('question_topics__question', filter=question_chain, distinct=True)
            ).order_by('topic').distinct()
            data['topics'] = TopicResource(topics, many=True, context={'request': request}).data

        return api_response(True, 'Fetched Successfully', data)


class ExamStoreView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamStore', request=ExamStoreSerializer)
    def post(self, request):
        serializer = ExamStoreSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        data = serializer.validated_data
        try:
            with transaction.atomic():
                exam = ExamTrail.objects.create(
                    user=request.user,
                    title=data.get('title') or 'Exam',
                    mode=data['exam_mode'],
                    question_mode=data['question_mode'],
                    is_timed_mode=data['is_timed_mode'],
                    duration_minutes=(data['duration_minutes'] or None) if data['is_timed_mode'] else None,
                    difficulty=Question.DIFFICULTY_BY_NAME.get(data['difficulty']),
                    shuffle_answers=data['randomize_answers'],
                    question_count=data['question_count'],
                )
                exam.categories.set(data['categories'])
                exam.sub_categories.set(data['sub_categories'])
                exam.sub_sub_categories.set(data['sub_sub_categories'])
                exam.sections.set(data['sections'])
                exam.topics.set(data['topics'])
                exam.save_details(randomize=data['randomize_questions'])
                return api_response(True, 'Created Successfully', {'exam_id': exam.id})
        except ValueError as e:
            return api_response(False, str(e), {}, 500)
        except Exception as e:
            return api_response(False, str(e), {}, 500)


class ExamResetView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamReset')
    def post(self, request):
        request.user.exam_trails.all().delete()
        return api_response(True, 'Exam data is cleared')


class ExamQuestionsView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamQuestions')
    def get(self, request):
        exam_id = request.query_params.get('exam_id', 0)
        try:
            exam = ExamTrail.objects.prefetch_related('details', 'details__question').get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        if exam.status != 'completed' and exam.is_expired():
            exam.finish()

        stages = exam.stages or []
        current_stage = exam.current_stage or 1

        if stages and len(stages) > 1:
            stage_question_ids = exam.get_current_stage_questions()
            stage_offset = sum(stages[i]['question_count'] for i in range(current_stage - 1))
            stage_count = stages[current_stage - 1].get('question_count', 40)
            stage_details = exam.details.filter(question_id__in=stage_question_ids)
            is_last = current_stage >= len(stages)
        else:
            stage_question_ids = list(exam.details.order_by('id').values_list('question_id', flat=True))
            stage_offset = 0
            stage_count = exam.question_count
            stage_details = exam.details.all()
            is_last = True

        data = {
            'exam': ShowExamTrialResource(exam).data,
            'questions': stage_question_ids,
            'details': ExamTrialDetailResource(stage_details, many=True).data,
            'lab_value': Setting.value_of('lab_value'),
            'current_stage': current_stage,
            'total_stages': len(stages) if stages else 1,
            'stage_offset': stage_offset,
            'stage_question_count': stage_count,
            'is_last_stage': is_last,
            'saved_question_ids': list(SavedQuestion.objects.filter(
                user=request.user, question_id__in=stage_question_ids,
            ).values_list('question_id', flat=True)),
        }
        return api_response(True, 'Exam data', data)


class ExamQuestionDetailView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamQuestionDetail')
    def get(self, request, question_id):
        # The answer is revealed according to the exam it is viewed in, so that exam is required.
        trail = ExamTrail.objects.filter(
            pk=request.query_params.get('exam_id') or 0,
            user=request.user,
            details__question_id=question_id,
        ).first()
        if not trail:
            return send_error('Question not found', {'QuestionNotFound': ['No question found for given question_id that belongs to this exam']})
        try:
            question = Question.objects.get(pk=question_id)
        except Question.DoesNotExist:
            return send_error('Question not found', {'QuestionNotFound': ['No question found']})
        data = QuestionResource(
            question, context={'request': request, 'reveal': trail.reveals_question(question_id)},
        ).data
        by_id = {answer['id']: answer for answer in data['answers']}
        # Options keep their written order when it matters: "All of the above" questions, and explanations
        # that name the answer by its letter ("Correct answer is: D) ..."), which shuffling would contradict.
        if not question.keep_answer_order and not LETTER_REFERENCE.search(strip_tags(question.notes or '')):
            data['answers'] = [by_id[aid] for aid in trail.answer_order(question_id, by_id)]
        return api_response(True, 'Exam data', {'question': data})


class ExamCurrentStageView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamCurrentStage')
    def get(self, request, exam_id):
        try:
            exam = ExamTrail.objects.prefetch_related('details').get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        stages = exam.stages or []
        current_stage = exam.current_stage or 1

        if not stages or len(stages) <= 1:
            answered = exam.details.filter(answer_id__isnull=False).count()
            return api_response(True, 'Exam stage data', {
                'exam': ShowExamTrialResource(exam).data,
                'current_stage': 1,
                'total_stages': 1,
                'stage_offset': 0,
                'stage_question_count': exam.question_count,
                'questions_answered_in_stage': answered,
                'is_stage_complete': answered >= exam.question_count,
                'is_last_stage': True,
                'can_advance': False,
            })

        stage_questions = exam.get_current_stage_questions()
        answered = exam.details.filter(question_id__in=stage_questions, answer_id__isnull=False).count()
        stage_offset = sum(stages[i]['question_count'] for i in range(current_stage - 1))
        stage_info = stages[current_stage - 1] if current_stage <= len(stages) else None
        stage_count = stage_info['question_count'] if stage_info else 40
        is_last = current_stage >= len(stages)
        is_complete = answered >= len(stage_questions)

        return api_response(True, 'Exam stage data', {
            'exam': ShowExamTrialResource(exam).data,
            'current_stage': current_stage,
            'total_stages': len(stages),
            'stage_offset': stage_offset,
            'stage_question_count': stage_count,
            'questions_answered_in_stage': answered,
            'is_stage_complete': is_complete,
            'is_last_stage': is_last,
            'can_advance': is_complete and not is_last,
            'stages': stages,
        })


class ExamAdvanceStageView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamAdvanceStage')
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        if exam.advance_to_next_stage():
            stages = exam.stages or []
            return api_response(True, 'Stage advanced', {
                'current_stage': exam.current_stage,
                'total_stages': len(stages),
            })
        return send_error('Cannot advance', {'CannotAdvance': ['Already on the last stage or no stages to advance']})


class ExamStageView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamStage')
    def get(self, request, exam_id, stage_number):
        try:
            exam = ExamTrail.objects.prefetch_related('details').get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        stages = exam.stages or []
        current_stage = exam.current_stage or 1
        stage_num = int(stage_number)

        if stages and len(stages) > 1:
            if stage_num < 1 or stage_num > len(stages):
                return send_error('Invalid stage', {'InvalidStage': ['Stage number out of range']})
            stage_question_ids = exam.get_stage_questions(stage_num)
            stage_offset = sum(stages[i]['question_count'] for i in range(stage_num - 1))
            stage_count = stages[stage_num - 1].get('question_count', 40)
            stage_details = exam.details.filter(question_id__in=stage_question_ids)
            is_last = current_stage >= len(stages)
        else:
            stage_question_ids = list(exam.details.order_by('id').values_list('question_id', flat=True))
            stage_offset = 0
            stage_count = exam.question_count
            stage_details = exam.details.all()
            stage_num = 1
            is_last = True

        data = {
            'exam': ShowExamTrialResource(exam).data,
            'questions': stage_question_ids,
            'details': ExamTrialDetailResource(stage_details, many=True).data,
            'lab_value': Setting.value_of('lab_value'),
            'current_stage': current_stage,
            'viewing_stage': stage_num,
            'total_stages': len(stages) if stages else 1,
            'stage_offset': stage_offset,
            'stage_question_count': stage_count,
            'is_last_stage': is_last,
            'is_readonly': exam.status == 'completed',
        }
        return api_response(True, 'Stage data', data)


class ExamStoreQuestionAnswerView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamStoreQuestionAnswer', request=StoreQuestionAnswerSerializer)
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        closed = reject_if_closed(exam)
        if closed:
            return closed

        serializer = StoreQuestionAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        for item in serializer.validated_data.get('answers', []):
            try:
                qid = int(item.get('question_id'))
                aid = int(item['answer_id']) if item.get('answer_id') not in (None, '') else None
            except (TypeError, ValueError):
                return send_error('Validation Errors', {'answers': ['question_id and answer_id must be numbers']}, 422)
            if aid is not None and not Answer.objects.filter(pk=aid, question_id=qid).exists():
                return send_error('Validation Errors', {'answer_id': [f'Answer {aid} does not belong to question {qid}']}, 422)
            ExamTrialDetail.objects.filter(exam_trail=exam, question_id=qid).update(
                answer_id=aid,
                is_correct=exam.grade(qid, aid),
                is_marked=item.get('is_marked') in (True, 'true', 1, '1'),
            )

        exam.finish()
        return api_response(True, 'Exam complete successfully', {
            'total_questions': exam.total_questions,
            'correct_answers': exam.correct_answers,
            'wrong_answers': exam.wrong_answers,
        })


class ExamStoreSingleQuestionAnswerView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamStoreSingleQuestionAnswer', request=StoreSingleQuestionAnswerSerializer)
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        closed = reject_if_closed(exam)
        if closed:
            return closed

        serializer = StoreSingleQuestionAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        qid = serializer.validated_data['question_id']
        aid = serializer.validated_data.get('answer_id')
        if not exam.details.filter(question_id=qid).exists():
            return send_error('Question not found', {'QuestionNotFound': ['This question is not part of this exam']}, 422)
        if aid is not None and not Answer.objects.filter(pk=aid, question_id=qid).exists():
            return send_error('Validation Errors', {'answer_id': ['This answer does not belong to the question']}, 422)

        is_correct = exam.grade(qid, aid)
        exam.details.filter(question_id=qid).update(
            answer_id=aid,
            is_correct=is_correct,
            is_marked=serializer.validated_data.get('is_marked', False),
        )

        # Scores are computed when the exam is finished; until then only tutor mode reveals grading.
        data = {'question_id': qid, 'answer_id': aid, 'is_correct': None}
        if exam.reveals_answers() and aid is not None:
            question = Question.objects.get(pk=qid)
            data.update({
                'is_correct': is_correct,
                'correct_answer_id': question.correct_answer_id,
                'notes': question.notes,
            })
        return api_response(True, 'Answer saved', data)


class ExamOverviewView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamOverview')
    def get(self, request, exam_id):
        try:
            exam = ExamTrail.objects.prefetch_related('details').get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        stages = exam.stages or []
        current_stage = exam.current_stage or 1
        all_ids = list(exam.details.order_by('id').values_list('question_id', flat=True))
        stages_data = []
        offset = 0
        for i, stage in enumerate(stages):
            stage_num = i + 1
            count = stage.get('question_count', 40)
            stage_qs = all_ids[offset:offset + count]
            answered = exam.details.filter(question_id__in=stage_qs, answer_id__isnull=False).count()
            if answered >= count and count > 0:
                status = 'completed'
            elif answered > 0:
                status = 'in_progress'
            else:
                status = 'available'
            stages_data.append({
                'stage': stage_num,
                'name': stage.get('name', f'Stage {stage_num}'),
                'question_count': count,
                'answered_count': answered,
                'status': status,
            })
            offset += count

        if not stages_data:
            answered = exam.details.filter(answer_id__isnull=False).count()
            stages_data.append({
                'stage': 1,
                'name': 'Stage 1',
                'question_count': exam.question_count,
                'answered_count': answered,
                'status': 'completed' if exam.status == 'completed' else ('in_progress' if answered > 0 else 'available'),
            })

        total_answered = exam.details.filter(answer_id__isnull=False).count()
        return api_response(True, 'Exam overview', {
            'exam': ShowExamTrialResource(exam).data,
            'current_stage': current_stage,
            'total_stages': len(stages) if stages else 1,
            'total_answered': total_answered,
            'is_completed': exam.status == 'completed',
            'stages': stages_data,
        })


class ExamFinishView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamFinish')
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        if exam.status != 'completed':
            exam.finish()
        return api_response(True, 'Exam finished', {
            'id': exam.id,
            'status': exam.status,
            'total_questions': exam.total_questions,
            'correct_answers': exam.correct_answers,
            'wrong_answers': exam.wrong_answers,
        })


class ExamAnalyticsView(BaseApiView):
    """Everything the result page shows, computed from the recorded attempt (apps.exams.analytics)."""
    permission_classes = [IsAuthenticated]

    @api_get('ExamAnalytics')
    def get(self, request, exam_id):
        from apps.exams import analytics

        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']}, 404)
        if exam.status != 'completed' and exam.is_expired():
            exam.finish()
        if not exam.reveals_answers():
            return send_error('Exam in progress', {'ExamInProgress': ['Results are available after the exam is submitted']}, 409)
        name = ' '.join(p for p in (request.user.first_name, request.user.last_name) if p)
        return api_response(True, 'Fetched Successfully', analytics.build(exam, name))


class ExamQuestionTimeView(BaseApiView):
    """Adds the seconds the student just spent on one question (sent by the player when leaving it)."""
    permission_classes = [IsAuthenticated]
    MAX_SECONDS_PER_VISIT = 30 * 60

    @api_post('ExamQuestionTime')
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']}, 404)
        if exam.status == 'completed':
            return api_response(True, 'Exam already submitted', {'recorded': False})
        try:
            question_id = int(request.data.get('question_id'))
            seconds = int(request.data.get('seconds'))
        except (TypeError, ValueError):
            return send_error('Validation Errors', {'seconds': ['question_id and seconds are required numbers']}, 422)
        seconds = max(0, min(seconds, self.MAX_SECONDS_PER_VISIT))
        updated = exam.details.filter(question_id=question_id).update(
            time_spent_seconds=Coalesce(F('time_spent_seconds'), Value(0)) + seconds,
        )
        return api_response(True, 'Recorded', {'recorded': bool(updated)})


class ExamRetakeView(BaseApiView):
    """A new attempt with the same settings and filters as this exam (questions drawn again)."""
    permission_classes = [IsAuthenticated]

    @api_post('ExamRetake')
    def post(self, request, exam_id):
        try:
            old = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']}, 404)
        try:
            with transaction.atomic():
                new = ExamTrail.objects.create(
                    user=request.user, title=old.title, mode=old.mode, question_mode=old.question_mode,
                    is_timed_mode=old.is_timed_mode, duration_minutes=old.duration_minutes, difficulty=old.difficulty,
                    shuffle_answers=old.shuffle_answers, question_count=old.total_questions or old.question_count,
                )
                new.categories.set(old.categories.all())
                new.sub_categories.set(old.sub_categories.all())
                new.sub_sub_categories.set(old.sub_sub_categories.all())
                new.sections.set(old.sections.all())
                new.topics.set(old.topics.all())
                new.save_details(randomize=True)
        except ValueError as e:
            return send_error(str(e), {'retake': [str(e)]}, 422)
        return api_response(True, 'Created Successfully', {'exam_id': new.id})
