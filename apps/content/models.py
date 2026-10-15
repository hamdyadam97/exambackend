from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    LEVEL_CATEGORY = 1
    LEVEL_SUB_CATEGORY = 2
    LEVEL_SUB_SUB_CATEGORY = 3
    LEVEL_CHOICES = [
        (LEVEL_CATEGORY, _('Category')),
        (LEVEL_SUB_CATEGORY, _('Sub Category')),
        (LEVEL_SUB_SUB_CATEGORY, _('Sub Sub Category')),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    icon = models.CharField(max_length=255, null=True, blank=True)
    is_new = models.BooleanField(default=False)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        db_column='parent_id',
        related_name='children',
        null=True,
        blank=True,
        verbose_name=_('Parent Category')
    )
    level = models.PositiveSmallIntegerField(
        choices=LEVEL_CHOICES,
        default=LEVEL_CATEGORY,
        help_text=_('Legacy level indicator: 1=category, 2=sub-category, 3=sub-sub-category')
    )
    order = models.PositiveIntegerField(default=0)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    foreground_color = models.CharField(max_length=50, null=True, blank=True)
    background_color = models.CharField(max_length=50, null=True, blank=True)
    is_top = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'categories'
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['level', 'order', 'name']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['parent', 'status']),
            models.Index(fields=['level', 'status']),
            models.Index(fields=['is_top', 'status']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_root(self):
        return self.parent is None

    @property
    def is_leaf(self):
        return not self.children.filter(status=self.ACTIVE).exists()

    def get_ancestors(self, include_self=False):
        ancestors = []
        node = self if include_self else self.parent
        while node:
            ancestors.insert(0, node)
            node = node.parent
        return ancestors

    def get_descendants(self, include_self=False):
        result = [self] if include_self else []
        queue = [self]
        while queue:
            node = queue.pop(0)
            for child in node.children.filter(status=self.ACTIVE):
                result.append(child)
                queue.append(child)
        return result


class QuestionsTopic(models.Model):
    topic = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='topics',
        null=True,
        blank=True,
        limit_choices_to={'level__in': [Category.LEVEL_CATEGORY, Category.LEVEL_SUB_CATEGORY]}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'questions_topics'
        verbose_name = _('Questions Topic')
        verbose_name_plural = _('Questions Topics')
        ordering = ['topic']
        indexes = [
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.topic


class ExamSection(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='exam_sections',
        null=True,
        blank=True
    )
    order = models.PositiveIntegerField(default=0)
    status = models.IntegerField(choices=list(Category.STATUS_CHOICES.items()), default=Category.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exam_section'
        verbose_name = _('Exam Section')
        verbose_name_plural = _('Exam Sections')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Blog(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=500, null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    description = models.TextField()
    image = models.URLField(max_length=500, null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='category_id',
        related_name='blogs',
        null=True,
        blank=True
    )
    author = models.CharField(max_length=255, null=True, blank=True)
    author_title = models.CharField(max_length=255, null=True, blank=True)
    author_image = models.URLField(max_length=500, null=True, blank=True)
    reading_time = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    tags = models.CharField(max_length=500, null=True, blank=True)
    topic = models.CharField(max_length=255, null=True, blank=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'blogs'
        verbose_name = _('Blog')
        verbose_name_plural = _('Blogs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.title


class BlogComment(models.Model):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    STATUS_CHOICES = [
        (PENDING, _('Pending')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
    ]

    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        db_column='blog_id',
        related_name='comments'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    content = models.TextField()
    status = models.IntegerField(choices=list(STATUS_CHOICES), default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blog_comments'
        verbose_name = _('Blog Comment')
        verbose_name_plural = _('Blog Comments')
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.name} on {self.blog}'


class Testimonial(models.Model):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    STATUS_CHOICES = [
        (PENDING, _('Pending')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    specialty = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    profile_image = models.URLField(max_length=500, null=True, blank=True)
    content = models.TextField()
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    is_verified = models.BooleanField(default=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='testimonials'
    )
    status = models.IntegerField(choices=list(STATUS_CHOICES), default=APPROVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'testimonials'
        verbose_name = _('Testimonial')
        verbose_name_plural = _('Testimonials')
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Instructor(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    name = models.CharField(max_length=255)
    image = models.URLField(max_length=500, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    specialization = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instructors'
    )
    years_of_experience = models.PositiveIntegerField(default=0)
    students_count = models.PositiveIntegerField(default=0)
    courses_count = models.PositiveIntegerField(default=0)
    certificates_count = models.PositiveIntegerField(default=0)
    facebook = models.URLField(max_length=500, null=True, blank=True)
    twitter = models.URLField(max_length=500, null=True, blank=True)
    linkedin = models.URLField(max_length=500, null=True, blank=True)
    rate = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'instructors'
        verbose_name = _('Instructor')
        verbose_name_plural = _('Instructors')
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.name


class Faq(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=255, null=True, blank=True)
    topic = models.CharField(max_length=100, default='general')
    order = models.PositiveIntegerField(default=0)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'faqs'
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.question


class Notification(models.Model):
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='NotificationReceipt',
        related_name='notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class NotificationReceipt(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        db_column='notification_id',
        related_name='receipts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='notification_receipts'
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_receipts'


class Partner(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    name = models.CharField(max_length=255)
    logo = models.URLField(max_length=500, null=True, blank=True)
    website_url = models.URLField(max_length=500, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'partners'
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.name


class AppInfo(models.Model):
    ios_version = models.CharField(max_length=50, null=True, blank=True)
    android_version = models.CharField(max_length=50, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    whatsapp = models.CharField(max_length=50, null=True, blank=True)
    facebook = models.URLField(max_length=500, null=True, blank=True)
    twitter = models.URLField(max_length=500, null=True, blank=True)
    instagram = models.URLField(max_length=500, null=True, blank=True)
    linkedin = models.URLField(max_length=500, null=True, blank=True)
    youtube = models.URLField(max_length=500, null=True, blank=True)
    map_url = models.URLField(max_length=1000, null=True, blank=True)
    working_hours = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'app_infos'
        verbose_name = _('App Info')
        verbose_name_plural = _('App Info')

    def __str__(self):
        return 'App Info'


class ContactMessage(models.Model):
    name = models.CharField(max_length=255, default='')
    email = models.EmailField(max_length=255, default='')
    mobile = models.CharField(max_length=50, null=True, blank=True)
    message = models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contact_messages'
        verbose_name = _('Contact Message')
        verbose_name_plural = _('Contact Messages')
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class SupportRequest(models.Model):
    OPEN = 'open'
    CLOSED = 'closed'
    # Backward-compatible aliases used in dashboard/seed scripts
    STATUS_OPEN = OPEN
    STATUS_CLOSED = CLOSED
    STATUS_CHOICES = [
        (OPEN, _('Open')),
        (CLOSED, _('Closed')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_requests',
        null=True,
        blank=True
    )
    question = models.ForeignKey(
        'exams.Question',
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='support_requests',
        null=True,
        blank=True
    )
    question_text = models.TextField(null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'support_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]


class AiInstruction(models.Model):
    question = models.ForeignKey(
        'exams.Question',
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='ai_instructions',
        null=True,
        blank=True
    )
    instructions = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_instructions'
        verbose_name = _('AI Instruction')
        verbose_name_plural = _('AI Instructions')
        ordering = ['-created_at']


class Certificate(models.Model):
    ACTIVE = 1
    INACTIVE = 0
    STATUS_CHOICES = {ACTIVE: _('Active'), INACTIVE: _('Inactive')}

    certificate_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    student_name = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates'
    )
    related_course = models.CharField(max_length=255, null=True, blank=True)
    instructor_name = models.CharField(max_length=255, null=True, blank=True)
    issuing_organization = models.CharField(max_length=255, default='RootsExams')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    image = models.URLField(max_length=500, null=True, blank=True)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=True)
    status = models.IntegerField(choices=list(STATUS_CHOICES.items()), default=ACTIVE)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'certificates'
        verbose_name = _('Certificate')
        verbose_name_plural = _('Certificates')
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['certificate_id']),
            models.Index(fields=['student_name']),
        ]

    def __str__(self):
        return f'{self.certificate_id} - {self.title}'


class Setting(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'settings'
        ordering = ['key']

    def __str__(self):
        return self.key

    @classmethod
    def value_of(cls, key, default=None):
        return cls.objects.filter(key=key).values_list('value', flat=True).first() or default
