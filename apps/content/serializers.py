"""
Content serializers.
"""
from rest_framework import serializers
from apps.content.models import (
    Category, QuestionsTopic, ExamSection,
    Blog, BlogComment, Testimonial, Notification, AppInfo, Partner,
    ContactMessage, SupportRequest, Instructor, Faq, AiInstruction, Setting,
    Certificate,
)


class CategoryResource(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()
    packages_count = serializers.SerializerMethodField()
    exams_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 'parent', 'level', 'order',
            'status', 'foreground_color', 'background_color',
            'is_top', 'is_new', 'children', 'questions_count', 'packages_count', 'exams_count',
        ]

    def get_children(self, obj):
        if hasattr(obj, 'prefetched_children'):
            return CategoryResource(obj.prefetched_children, many=True).data
        return CategoryResource(obj.children.filter(status=Category.ACTIVE), many=True).data

    def get_questions_count(self, obj):
        if hasattr(obj, 'questions_count'):
            return obj.questions_count or 0
        if obj.level == Category.LEVEL_CATEGORY:
            return obj.questions.filter(status=1).count()
        if obj.level == Category.LEVEL_SUB_CATEGORY:
            return obj.questions_as_sub.filter(status=1).count()
        if obj.level == Category.LEVEL_SUB_SUB_CATEGORY:
            return obj.questions_as_sub_sub.filter(status=1).count()
        return 0

    def get_packages_count(self, obj):
        if hasattr(obj, 'packages_count'):
            return obj.packages_count or 0
        if obj.level == Category.LEVEL_CATEGORY:
            return obj.packages.filter(status=1, deleted_at__isnull=True).count()
        return 0

    def get_exams_count(self, obj):
        if hasattr(obj, 'exams_count'):
            return obj.exams_count or 0
        from django.apps import apps
        Exam = apps.get_model('exams', 'Exam')
        if obj.level == Category.LEVEL_CATEGORY:
            return obj.exams.filter(status=Exam.ACTIVE, deleted_at__isnull=True).count()
        if obj.level == Category.LEVEL_SUB_CATEGORY:
            return obj.exams_as_sub.filter(status=Exam.ACTIVE, deleted_at__isnull=True).count()
        if obj.level == Category.LEVEL_SUB_SUB_CATEGORY:
            return obj.exams_as_sub_sub.filter(status=Exam.ACTIVE, deleted_at__isnull=True).count()
        return 0


class TopicResource(serializers.ModelSerializer):
    name = serializers.CharField(source='topic', read_only=True)
    category_id = serializers.IntegerField(read_only=True)
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = QuestionsTopic
        fields = ['id', 'name', 'category_id', 'questions_count']

    def get_questions_count(self, obj):
        if hasattr(obj, 'questions_count'):
            return obj.questions_count or 0
        return obj.question_topics.filter(question__status=1, question__deleted_at__isnull=True).count()


class SectionResource(serializers.ModelSerializer):
    category_id = serializers.IntegerField(read_only=True)
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamSection
        fields = ['id', 'name', 'category_id', 'questions_count']

    def get_questions_count(self, obj):
        if hasattr(obj, 'questions_count'):
            return obj.questions_count or 0
        return obj.exam_section_links.filter(question__status=1, question__deleted_at__isnull=True).count()


class BlogCommentResource(serializers.ModelSerializer):
    blog = serializers.PrimaryKeyRelatedField(queryset=Blog.objects.all(), write_only=True)

    class Meta:
        model = BlogComment
        fields = ['id', 'blog_id', 'blog', 'name', 'email', 'content', 'status', 'created_at']
        extra_kwargs = {
            'blog_id': {'read_only': True},
            'status': {'read_only': True},
        }


class BlogResource(serializers.ModelSerializer):
    category = CategoryResource(read_only=True)
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = [
            'id', 'category', 'title', 'subtitle', 'description', 'image', 'author',
            'author_title', 'author_image', 'topic', 'reading_time', 'views', 'tags',
            'status', 'comments', 'created_at', 'updated_at',
        ]

    def get_comments(self, obj):
        comments = obj.comments.filter(status=BlogComment.APPROVED)
        return BlogCommentResource(comments, many=True).data


class TestimonialResource(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = [
            'id', 'user_id', 'name', 'email', 'specialty', 'country',
            'profile_image', 'is_verified', 'content', 'rating', 'status',
            'created_at',
        ]


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'mobile', 'message']


class SupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportRequest
        fields = ['question_id', 'question_text', 'message']


class InstructorResource(serializers.ModelSerializer):
    category = CategoryResource(read_only=True)

    class Meta:
        model = Instructor
        fields = [
            'id', 'name', 'title', 'image', 'specialization', 'category', 'bio',
            'years_of_experience', 'students_count', 'courses_count',
            'certificates_count', 'rate', 'facebook', 'twitter', 'linkedin',
            'is_featured', 'order', 'status', 'created_at',
        ]


class FaqResource(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ['id', 'question', 'answer', 'category', 'order', 'status', 'created_at']


class CertificateResource(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = [
            'id', 'certificate_id', 'title', 'description', 'student_name',
            'related_course', 'instructor_name', 'issuing_organization',
            'issue_date', 'expiry_date', 'image', 'pdf_url',
            'is_featured', 'is_verified', 'status', 'order', 'created_at',
        ]


class PartnerResource(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ['id', 'name', 'logo', 'website_url', 'order', 'status', 'created_at']


class AppInfoResource(serializers.ModelSerializer):
    class Meta:
        model = AppInfo
        fields = [
            'id', 'ios_version', 'android_version', 'map_url', 'address',
            'phone', 'whatsapp', 'email', 'working_hours',
        ]


class NotificationResource(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'description']


class AiInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiInstruction
        fields = ['id', 'question_id', 'instructions', 'is_default']


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ['id', 'key', 'value']
