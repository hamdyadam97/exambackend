"""
Content API views: home, categories, blogs, testimonials, support, chat.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q, Prefetch
from apps.content.models import (
    Category, QuestionsTopic, ExamSection,
    Blog, BlogComment, Testimonial, ContactMessage, SupportRequest,
    AppInfo, Partner, Notification, NotificationReceipt, AiInstruction, Setting,
)
from apps.content.serializers import (
    CategoryResource, TopicResource, SectionResource, BlogResource,
    BlogCommentResource, TestimonialResource, ContactMessageSerializer,
    SupportRequestSerializer,
    AppInfoResource, PartnerResource, NotificationResource,
)
from apps.exams.models import Question
from apps.packages.models import Package
from apps.packages.serializers import PackageResource
from apps.core.utils import api_response, send_response, send_error, api_get, api_post
from apps.core.services import OpenAiService


class BaseApiView(APIView):
    pass


class LandingView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Landing')
    def get(self, request):
        categories = Category.objects.filter(
            status=1, level=Category.LEVEL_CATEGORY
        ).annotate(
            questions_count=Count('questions', filter=Q(questions__status=1)),
            packages_count=Count('packages', filter=Q(packages__status=Package.ACTIVE, packages__deleted_at__isnull=True))
        ).order_by('name')
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')[:10]
        blogs = Blog.objects.filter(status=1).order_by('-created_at')[:6]
        packages = Package.objects.filter(status=1, is_trial=False).order_by('-created_at')[:6]
        partners = Partner.objects.filter(status=Partner.ACTIVE).order_by('order', 'name')
        app_info = AppInfo.objects.first()

        return send_response('success', {
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
            'testimonials': TestimonialResource(testimonials, many=True).data,
            'blogs': BlogResource(blogs, many=True, context={'request': request}).data,
            'packages': PackageResource(packages, many=True, context={'request': request}).data,
            'partners': PartnerResource(partners, many=True, context={'request': request}).data,
            'app_info': AppInfoResource(app_info, context={'request': request}).data if app_info else None,
        })


class HomeView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('Home')
    def get(self, request):
        user = request.user
        categories_count = user.subscribed_categories().count()
        subcategories_count = user.subscribed_sub_categories().count()
        active_subs = user.active_subscriptions().select_related('package').order_by('end_date')
        # Exam-mode trails still in progress are excluded so their grading stays hidden.
        answers = user.exam_trails.filter(Q(status='completed') | Q(mode='tatur')).aggregate(
            answered=Count('details', filter=Q(details__answer_id__isnull=False)),
            correct=Count('details', filter=Q(details__is_correct=True)),
        )
        total_answered = answers['answered'] or 0
        total_correct = answers['correct'] or 0

        completed = user.exam_trails.filter(status='completed', total_questions__gt=0)
        scores = [round(t.correct_answers * 100 / t.total_questions) for t in completed.only('correct_answers', 'total_questions')]
        current = active_subs.first()

        return send_response('success', {
            'categories_count': categories_count,
            'subcategories_count': subcategories_count,
            'active_subscriptions': active_subs.count(),
            'total_answered': total_answered,
            'total_correct': total_correct,
            'success_rate': round(total_correct * 100 / total_answered) if total_answered else 0,
            'completed_exams': len(scores),
            'in_progress_exams': user.exam_trails.exclude(status='completed').count(),
            'average_score': round(sum(scores) / len(scores)) if scores else 0,
            'best_score': max(scores) if scores else 0,
            'current_package': {
                'name': current.package.name,
                'end_date': current.end_date,
            } if current else None,
        })


class ContactView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('Contact', request=ContactMessageSerializer)
    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)
        serializer.save()
        return send_response('Message sent successfully', {})


class CategoriesView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Categories')
    def get(self, request):
        categories = Category.objects.filter(
            status=1, level=Category.LEVEL_CATEGORY
        ).prefetch_related(
            Prefetch('children', queryset=Category.objects.filter(status=1), to_attr='prefetched_children')
        ).annotate(
            questions_count=Count('questions', filter=Q(questions__status=1))
        ).order_by('name')
        return api_response(True, 'Fetched Successfully', {
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
        })


class CategoryDetailView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('CategoryDetail')
    def get(self, request, pk):
        try:
            category = Category.objects.prefetch_related(
                Prefetch('children', queryset=Category.objects.filter(status=1), to_attr='prefetched_children')
            ).get(pk=pk, status=1)
        except Category.DoesNotExist:
            return send_error('Category not found', {}, 404)
        return api_response(True, 'Fetched Successfully', {
            'category': CategoryResource(category, context={'request': request}).data,
        })


class SubCategoriesForCategoryView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('SubCategoriesForCategory')
    def get(self, request, pk):
        sub_categories = Category.objects.filter(
            parent_id=pk, status=1, level=Category.LEVEL_SUB_CATEGORY
        ).annotate(
            questions_count=Count('questions_as_sub', filter=Q(questions_as_sub__status=1))
        ).order_by('name')
        return api_response(True, 'Fetched Successfully', {
            'sub_categories': CategoryResource(sub_categories, many=True, context={'request': request}).data,
        })


class GetCategoryView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('GetCategory')
    def get(self, request):
        categories = request.user.subscribed_categories()
        return api_response(True, 'Fetched Successfully', {
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
        })


class GetSubcategoryView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('GetSubcategory')
    def get(self, request):
        sub_categories = request.user.subscribed_sub_categories()
        return api_response(True, 'Fetched Successfully', {
            'sub_categories': CategoryResource(sub_categories, many=True, context={'request': request}).data,
        })


class UserNotificationsView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('UserNotifications')
    def get(self, request):
        notifications = Notification.objects.filter(
            target_users=request.user,
            deleted_at__isnull=True,
        ).order_by('-created_at')[:20]

        result = []
        for note in notifications:
            receipt = NotificationReceipt.objects.filter(notification=note, user=request.user).first()
            result.append({
                'id': note.id,
                'title': note.title,
                'description': note.description,
                'is_read': receipt.is_read if receipt else False,
                'created_at': note.created_at,
            })

        return api_response(True, 'Fetched Successfully', {'notifications': result})


class BlogsView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Blogs')
    def get(self, request):
        blogs = Blog.objects.filter(status=1).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'blogs': BlogResource(blogs, many=True, context={'request': request}).data,
        })


class BlogDetailView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('BlogDetail')
    def get(self, request, pk):
        try:
            blog = Blog.objects.get(pk=pk, status=1)
        except Blog.DoesNotExist:
            return send_error('Blog not found', {}, 404)
        blog.views += 1
        blog.save(update_fields=['views'])
        return api_response(True, 'Fetched Successfully', {
            'blog': BlogResource(blog, context={'request': request}).data,
        })


class BlogCommentView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('BlogComments')
    def get(self, request, pk):
        comments = BlogComment.objects.filter(
            blog_id=pk, status=BlogComment.APPROVED
        ).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'comments': BlogCommentResource(comments, many=True).data,
        })

    @api_post('BlogComments', request=BlogCommentResource)
    def post(self, request, pk):
        data = request.data.copy()
        data['blog'] = pk
        serializer = BlogCommentResource(data=data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)
        serializer.save(status=BlogComment.PENDING)
        return send_response('Comment submitted successfully and awaiting approval', {
            'comment': serializer.data,
        })


class TestimonialsView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Testimonials')
    def get(self, request):
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')
        return api_response(True, 'Fetched Successfully', {
            'testimonials': TestimonialResource(testimonials, many=True).data,
        })

    @api_post('Testimonials', request=TestimonialResource)
    def post(self, request):
        data = request.data.copy()
        if request.user.is_authenticated:
            data['user_id'] = request.user.id
        serializer = TestimonialResource(data=data)
        name = data.get('name')
        content = data.get('content')
        if not name or not content:
            return send_error('Validation Errors', {'name': ['Name is required'], 'content': ['Content is required']}, 422)
        testimonial = Testimonial.objects.create(
            user_id=data.get('user_id'),
            name=name,
            email=data.get('email'),
            content=content,
            rating=data.get('rating'),
        )
        return api_response(True, 'Testimonial submitted successfully', {
            'testimonial': TestimonialResource(testimonial).data,
        })


class SupportView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('Support', request=SupportRequestSerializer)
    def post(self, request):
        serializer = SupportRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return send_error('Validation Errors', serializer.errors, 422)
        SupportRequest.objects.create(user=request.user, **serializer.validated_data)
        return send_response('Support request sent', {})


class ChatView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_post('Chat')
    def post(self, request):
        question_text = request.data.get('question_text', '')
        selected_answer = request.data.get('selected_answer', '')
        correct_answer = request.data.get('correct_answer', '')
        notes = request.data.get('notes', '')

        explanation = OpenAiService.explain_question(question_text, selected_answer, correct_answer, notes)
        if explanation is None:
            explanation = notes or 'No explanation available.'
        return send_response('success', {'response': explanation})


class QuestionBanksView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('QuestionBanks')
    def get(self, request):
        categories = Category.objects.filter(
            status=1, level=Category.LEVEL_CATEGORY
        ).annotate(
            questions_count=Count('questions', filter=Q(questions__status=1))
        ).order_by('name')
        return api_response(True, 'Fetched Successfully', {
            'categories': CategoryResource(categories, many=True, context={'request': request}).data,
        })


class PaymentTypesView(BaseApiView):
    permission_classes = [IsAuthenticated]

    @api_get('PaymentTypes')
    def get(self, request):
        from apps.payments.models import PaymentType
        from apps.payments.serializers import PaymentTypeResource
        types = PaymentType.objects.filter(status=1)
        return api_response(True, 'Fetched Successfully', {
            'payment_types': PaymentTypeResource(types, many=True).data,
        })
