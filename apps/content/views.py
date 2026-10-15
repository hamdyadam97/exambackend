"""
Content API views: home, categories, blogs, testimonials, support, chat.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q, Prefetch
from apps.content.models import (
    Category, QuestionsTopic, ExamSection,
    Blog, BlogComment, Testimonial, ContactMessage, SupportRequest, Instructor,
    Faq, AppInfo, Partner, Notification, NotificationReceipt, AiInstruction, Setting,
    Certificate,
)
from apps.content.serializers import (
    CategoryResource, TopicResource, SectionResource, BlogResource,
    BlogCommentResource, TestimonialResource, ContactMessageSerializer,
    SupportRequestSerializer, InstructorResource, FaqResource,
    AppInfoResource, PartnerResource, NotificationResource,
    CertificateResource,
)
from apps.exams.models import Question
from apps.packages.models import Package
from apps.users.models import User
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
        active_subscriptions = user.active_subscriptions().count()
        total_answered = user.exam_trails.aggregate(
            total=Count('details', filter=Q(details__answer_id__isnull=False))
        )['total'] or 0

        return send_response('success', {
            'categories_count': categories_count,
            'subcategories_count': subcategories_count,
            'active_subscriptions': active_subscriptions,
            'total_answered': total_answered,
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


class InstructorsView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('Instructors')
    def get(self, request):
        instructors = Instructor.objects.filter(status=Instructor.ACTIVE)
        featured = instructors.filter(is_featured=True).order_by('order', '-created_at')[:6]
        all_instructors = instructors.order_by('-is_featured', 'order', '-created_at')
        faqs = Faq.objects.filter(status=Faq.ACTIVE).order_by('order', '-created_at')[:10]
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')[:10]

        from django.db.models import Sum
        stats = Instructor.objects.filter(status=Instructor.ACTIVE).aggregate(
            total_experience=Sum('years_of_experience'),
            certificates=Sum('certificates_count'),
        )

        return api_response(True, 'Fetched Successfully', {
            'featured': InstructorResource(featured, many=True, context={'request': request}).data,
            'instructors': InstructorResource(all_instructors, many=True, context={'request': request}).data,
            'faqs': FaqResource(faqs, many=True).data,
            'testimonials': TestimonialResource(testimonials, many=True).data,
            'stats': {
                'total_instructors': instructors.count(),
                'total_students': User.objects.filter(role_type=User.ROLE_USER, status=User.ACTIVE).count(),
                'total_courses': Package.objects.filter(status=Package.ACTIVE, deleted_at__isnull=True).count(),
                'certificates_issued': stats['certificates'] or 0,
                'years_of_experience': stats['total_experience'] or 0,
            },
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


class CertificatesPageView(BaseApiView):
    permission_classes = [AllowAny]

    @api_get('CertificatesPage')
    def get(self, request):
        certificates = Certificate.objects.filter(status=Certificate.ACTIVE, deleted_at__isnull=True)
        featured = certificates.filter(is_featured=True).order_by('order', '-created_at')[:6]
        all_certs = certificates.order_by('order', '-created_at')
        faqs = Faq.objects.filter(status=Faq.ACTIVE).order_by('order', '-created_at')[:10]
        testimonials = Testimonial.objects.filter(status=Testimonial.APPROVED).order_by('-created_at')[:6]

        stats = {
            'certificates_issued': certificates.count(),
            'certified_students': certificates.values('student_name').distinct().count() or certificates.values('user').distinct().count(),
            'partner_organizations': Partner.objects.filter(status=Partner.ACTIVE).count(),
            'available_programs': Package.objects.filter(status=Package.ACTIVE, deleted_at__isnull=True).count(),
        }

        return api_response(True, 'Fetched Successfully', {
            'featured': CertificateResource(featured, many=True, context={'request': request}).data,
            'certificates': CertificateResource(all_certs, many=True, context={'request': request}).data,
            'faqs': FaqResource(faqs, many=True).data,
            'testimonials': TestimonialResource(testimonials, many=True).data,
            'stats': stats,
        })


class CertificateVerifyView(BaseApiView):
    permission_classes = [AllowAny]

    @api_post('CertificateVerify')
    def post(self, request):
        certificate_id = request.data.get('certificate_id', '').strip()
        student_name = request.data.get('student_name', '').strip()
        if not certificate_id:
            return send_error('Validation error', {'certificate_id': ['Certificate ID is required']})

        qs = Certificate.objects.filter(certificate_id=certificate_id, status=Certificate.ACTIVE, deleted_at__isnull=True)
        if student_name:
            qs = qs.filter(student_name__icontains=student_name)

        certificate = qs.first()
        if not certificate:
            return send_error('Certificate not found', {'certificate': ['No verified certificate matches the provided details']})

        return api_response(True, 'Certificate verified', {
            'certificate': CertificateResource(certificate, context={'request': request}).data,
        })
