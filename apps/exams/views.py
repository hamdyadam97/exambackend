"""
Exam API views.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.db.models import Count, Q
from apps.exams.models import (
    Question, Answer, Exam, ExamTrail, ExamTrialDetail, UserExam, exam_classification_q,
)
from apps.exams.serializers import (
    QuestionResource, ExamResource, ExamDetailResource, ExamTrialResource, ExamTrialIndexResource,
    ExamTrialDetailResource, ShowExamTrialResource, ExamStoreSerializer,
    StoreQuestionAnswerSerializer, StoreSingleQuestionAnswerSerializer,
)
from apps.content.models import Category, ExamSection, QuestionsTopic, Faq, Testimonial
from apps.content.serializers import (
    CategoryResource, SectionResource, TopicResource, FaqResource, TestimonialResource,
)
from apps.core.utils import api_response, send_response, send_error, api_get, api_post
from apps.content.models import Setting


class BaseApiView(APIView):
    pass


class ExamsPageView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('ExamsPage')
    def get(self, request):
        exams = Exam.objects.filter(status=Exam.ACTIVE, deleted_at__isnull=True)
        featured = exams.filter(is_featured=True).order_by('order', '-created_at')[:6]
        all_exams = exams.order_by('order', '-created_at')
        categories = Category.objects.filter(status=Category.ACTIVE, level=Category.LEVEL_CATEGORY).annotate(
            exams_count=Count('exams', filter=Q(exams__status=Exam.ACTIVE, exams__deleted_at__isnull=True))
        ).order_by('name')
        faqs = Faq.objects.filter(status=Faq.ACTIVE).order_by('order', '-created_at')[:10]
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')[:10]

        stats = exams.aggregate(
            total_exams=Count('id'),
            total_questions=Count('exam_questions', filter=Q(exam_questions__deleted_at__isnull=True)),
        )

        data = {
            'featured': ExamResource(featured, many=True, context={'request': request}).data,
            'exams': ExamResource(all_exams, many=True, context={'request': request}).data,
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
            'faqs': FaqResource(faqs, many=True).data,
            'testimonials': TestimonialResource(testimonials, many=True).data,
            'stats': {
                'total_exams': stats['total_exams'] or 0,
                'total_questions': stats['total_questions'] or 0,
                'total_attempts': UserExam.objects.count(),
                'certificates_issued': stats['total_exams'] or 0,
            },
        }

        if request.user and request.user.is_authenticated:
            user_exams = UserExam.objects.filter(user=request.user, deleted_at__isnull=True).select_related('exam')
            data['upcoming'] = ExamResource(
                [ue.exam for ue in user_exams.filter(status__in=[UserExam.STATUS_NEW, UserExam.STATUS_IN_PROGRESS])],
                many=True, context={'request': request}
            ).data
            data['completed'] = ExamResource(
                [ue.exam for ue in user_exams.filter(status=UserExam.STATUS_SUBMITTED)],
                many=True, context={'request': request}
            ).data

        return api_response(True, 'Fetched Successfully', data)


class ExamDetailPageView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('ExamDetailPage')
    def get(self, request, pk):
        try:
            exam = Exam.objects.get(pk=pk, status=Exam.ACTIVE, deleted_at__isnull=True)
        except Exam.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given id']})

        faqs = Faq.objects.filter(status=Faq.ACTIVE).order_by('order', '-created_at')[:10]

        data = {
            'exam': ExamDetailResource(exam, context={'request': request}).data,
            'faqs': FaqResource(faqs, many=True).data,
        }
        return api_response(True, 'Fetched Successfully', data)


class ExamListView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamList')
    def get(self, request):
        exams = ExamTrail.objects.filter(user=request.user).prefetch_related('categories').annotate(
            details_count=Count('details', filter=Q(details__answer_id__isnull=False))
        ).order_by('-created_at')
        from apps.core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(exams, request)
        data = {
            'exams': ExamTrialIndexResource(page, many=True, context={'request': request}).data,
            'pagination': {
                'count': paginator.page.paginator.count,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
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
        user = request.user
        root_ids = list(user.subscribed_categories().values_list('id', flat=True))
        categories = Category.objects.filter(id__in=root_ids, status=1).annotate(
            questions_count=Count('questions', filter=exam_classification_q('questions'), distinct=True)
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
        chain = exam_classification_q('questions_as_sub', category_ids=category_ids)
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

        chain = exam_classification_q(
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

        # Sections may be attached to any level of the selected category tree,
        # so consider the selected specialty, category and sub-category ids.
        selected_category_ids = set(category_ids + sub_category_ids + sub_sub_category_ids)
        sections = ExamSection.objects.filter(category_id__in=selected_category_ids)

        # The section count is cumulative: every classification level selected
        # above the section must match, plus a link to this section — the same
        # chain ExamTrail.get_question_query builds when drawing questions.
        question_chain = exam_classification_q(
            'exam_section_links__question',
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
        )

        sections = sections.filter(question_chain).annotate(
            questions_count=Count('exam_section_links__question', filter=question_chain, distinct=True)
        ).order_by('name').distinct()

        # Total of the distinct questions available across all listed sections,
        # i.e. what the exam would draw if every listed section were selected.
        section_ids = list(sections.values_list('id', flat=True))
        total_filter = exam_classification_q(
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
            section_ids=section_ids,
        )
        total = Question.objects.filter(total_filter).count() if section_ids else 0

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
        question_chain = exam_classification_q(
            'question_topics__question',
            category_ids=category_ids,
            sub_category_ids=sub_category_ids,
            sub_sub_category_ids=sub_sub_category_ids,
            section_ids=section_ids,
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
            chain = exam_classification_q('questions_as_sub', category_ids=cids)
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
            rchain = exam_classification_q(
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
            sections = ExamSection.objects.filter(category_id__in=selected_category_ids)

            question_chain = exam_classification_q(
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
            total_filter = exam_classification_q(
                category_ids=cids,
                sub_category_ids=scids,
                sub_sub_category_ids=sscids,
                section_ids=sids_for_total,
            )
            total = Question.objects.filter(total_filter).count() if sids_for_total else 0
            data['total_questions'] = total
            data['total_stages'] = (total + 39) // 40 if total > 0 else 0

        if section_ids:
            try:
                sids = [int(x) for x in section_ids]
            except ValueError:
                sids = []
            question_chain = exam_classification_q(
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
                    question_count=data['question_count'],
                )
                exam.categories.set(data['categories'])
                exam.sub_categories.set(data['sub_categories'])
                exam.sub_sub_categories.set(data['sub_sub_categories'])
                exam.sections.set(data['sections'])
                exam.topics.set(data['topics'])
                exam.save_details()
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
        }
        return api_response(True, 'Exam data', data)


class ExamQuestionDetailView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('ExamQuestionDetail')
    def get(self, request, question_id):
        owns = ExamTrail.objects.filter(
            user=request.user,
            details__question_id=question_id
        ).exists()
        if not owns:
            return send_error('Question not found', {'QuestionNotFound': ['No question found for given question_id that belongs to your exams']})
        try:
            question = Question.objects.get(pk=question_id)
        except Question.DoesNotExist:
            return send_error('Question not found', {'QuestionNotFound': ['No question found']})
        return api_response(True, 'Exam data', {
            'question': QuestionResource(question, context={'request': request}).data,
        })


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

        serializer = StoreQuestionAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        for item in serializer.validated_data.get('answers', []):
            qid = item.get('question_id')
            aid = item.get('answer_id')
            is_correct = item.get('is_correct') in (True, 'true', 1, '1')
            is_marked = item.get('is_marked') in (True, 'true', 1, '1')
            ExamTrialDetail.objects.filter(exam_trail=exam, question_id=qid).update(
                answer_id=aid,
                is_correct=is_correct,
                is_marked=is_marked,
            )

        total = exam.details.count()
        correct = exam.details.filter(is_correct=True).count()
        wrong = total - correct
        exam.total_questions = total
        exam.correct_answers = correct
        exam.wrong_answers = wrong
        exam.status = 'completed'
        exam.save()
        return api_response(True, 'Exam complete successfully', {
            'total_questions': total,
            'correct_answers': correct,
            'wrong_answers': wrong,
        })


class ExamStoreSingleQuestionAnswerView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('ExamStoreSingleQuestionAnswer', request=StoreSingleQuestionAnswerSerializer)
    def post(self, request, exam_id):
        try:
            exam = ExamTrail.objects.get(pk=exam_id, user=request.user)
        except ExamTrail.DoesNotExist:
            return send_error('Exam not found', {'ExamNotFound': ['No exam found for given exam_id']})

        serializer = StoreSingleQuestionAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)

        ExamTrialDetail.objects.filter(
            exam_trail=exam,
            question_id=serializer.validated_data['question_id']
        ).update(
            answer_id=serializer.validated_data.get('answer_id'),
            is_correct=serializer.validated_data.get('is_correct', False),
            is_marked=serializer.validated_data.get('is_marked', False),
        )

        total = exam.details.count()
        correct = exam.details.filter(is_correct=True).count()
        wrong = total - correct
        exam.total_questions = total
        exam.correct_answers = correct
        exam.wrong_answers = wrong
        exam.save()
        return api_response(True, 'Exam complete successfully', {
            'total_questions': total,
            'correct_answers': correct,
            'wrong_answers': wrong,
        })


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

        exam.status = 'completed'
        total = exam.details.count()
        correct = exam.details.filter(is_correct=True).count()
        exam.total_questions = total
        exam.correct_answers = correct
        exam.wrong_answers = total - correct
        exam.save()
        return api_response(True, 'Exam finished', {
            'id': exam.id,
            'status': exam.status,
            'total_questions': total,
            'correct_answers': correct,
            'wrong_answers': total - correct,
        })


class LegacyExamListView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('LegacyExamList')
    def get(self, request):
        exams = Exam.objects.filter(status=1).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'exams': [{'id': e.id, 'title': e.title, 'description': e.description, 'score': e.score} for e in exams],
        })
