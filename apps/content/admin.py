from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from apps.core.admin_site import admin_site
from apps.content.models import (
    Category, QuestionsTopic, ExamSection,
    Blog, BlogComment, Testimonial, Notification, NotificationReceipt, AppInfo,
    ContactMessage, SupportRequest, Instructor, Faq, AiInstruction, Setting,
    Certificate,
)


class CategoryInline(admin.TabularInline):
    model = Category
    fk_name = 'parent'
    extra = 1
    fields = ['name', 'level', 'order', 'status', 'is_top']
    show_change_link = True
    autocomplete_fields = ['parent']


class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'level', 'parent', 'order',
        'status', 'is_top', 'children_count', 'created_at',
    ]
    list_filter = ['status', 'level', 'is_top']
    search_fields = ['name']
    ordering = ['level', 'order', 'name']
    inlines = [CategoryInline]
    autocomplete_fields = ['parent']
    actions = ['activate', 'deactivate']
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('parent').annotate(children_count=Count('children'))

    @admin.display(description=_('Name'))
    def display_name(self, obj):
        indent = '— ' * (obj.level - 1) if obj.level else ''
        return f"{indent}{obj.name}"

    @admin.display(description=_('Sub-categories'))
    def children_count(self, obj):
        return obj.children_count

    @admin.action(description=_('Activate selected categories'))
    def activate(self, request, queryset):
        queryset.update(status=Category.ACTIVE)

    @admin.action(description=_('Deactivate selected categories'))
    def deactivate(self, request, queryset):
        queryset.update(status=Category.INACTIVE)



admin_site.register(Category, CategoryAdmin)
class QuestionsTopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'category', 'created_at']
    list_filter = ['category__level', 'category']
    search_fields = ['topic', 'category__name']
    autocomplete_fields = ['category']
    list_select_related = ['category']



admin_site.register(QuestionsTopic, QuestionsTopicAdmin)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'created_at']
    list_filter = ['category__level', 'category']
    search_fields = ['name', 'category__name']
    autocomplete_fields = ['category']
    list_select_related = ['category']



admin_site.register(ExamSection, ExamSectionAdmin)
class BlogAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'description']
    autocomplete_fields = ['category']
    list_select_related = ['category']
    date_hierarchy = 'created_at'
    actions = ['publish', 'unpublish']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Publish selected blogs'))
    def publish(self, request, queryset):
        queryset.update(status=Blog.ACTIVE)

    @admin.action(description=_('Unpublish selected blogs'))
    def unpublish(self, request, queryset):
        queryset.update(status=Blog.INACTIVE)



admin_site.register(Blog, BlogAdmin)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'blog', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'content', 'blog__title']
    autocomplete_fields = ['blog']
    date_hierarchy = 'created_at'
    actions = ['approve', 'reject']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Approve selected comments'))
    def approve(self, request, queryset):
        queryset.update(status=BlogComment.APPROVED)

    @admin.action(description=_('Reject selected comments'))
    def reject(self, request, queryset):
        queryset.update(status=BlogComment.REJECTED)


admin_site.register(BlogComment, BlogCommentAdmin)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating', 'created_at']
    search_fields = ['name', 'email', 'content']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    actions = ['approve', 'reject']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Approve selected testimonials'))
    def approve(self, request, queryset):
        queryset.update(status=Testimonial.APPROVED)

    @admin.action(description=_('Reject selected testimonials'))
    def reject(self, request, queryset):
        queryset.update(status=Testimonial.REJECTED)



admin_site.register(Testimonial, TestimonialAdmin)
class NotificationReceiptInline(admin.TabularInline):
    model = NotificationReceipt
    extra = 0
    readonly_fields = ['created_at']
    autocomplete_fields = ['user']


class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'receipt_count', 'created_at']
    search_fields = ['title', 'description']
    inlines = [NotificationReceiptInline]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(receipt_count=Count('receipts'))

    @admin.display(description=_('Receipts'))
    def receipt_count(self, obj):
        return obj.receipt_count



admin_site.register(Notification, NotificationAdmin)
class AppInfoAdmin(admin.ModelAdmin):
    list_display = ['ios_version', 'android_version', 'created_at']
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(AppInfo, AppInfoAdmin)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'mobile', 'created_at']
    search_fields = ['name', 'email', 'message']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(ContactMessage, ContactMessageAdmin)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__phone', 'question_text', 'message']
    autocomplete_fields = ['user', 'question']
    date_hierarchy = 'created_at'
    actions = ['close_requests', 'reopen_requests']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Close selected support requests'))
    def close_requests(self, request, queryset):
        queryset.update(status=SupportRequest.STATUS_CLOSED)

    @admin.action(description=_('Reopen selected support requests'))
    def reopen_requests(self, request, queryset):
        queryset.update(status=SupportRequest.STATUS_OPEN)



admin_site.register(SupportRequest, SupportRequestAdmin)
class InstructorAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'title', 'specialization', 'category', 'years_of_experience',
        'students_count', 'courses_count', 'rate', 'is_featured', 'status', 'created_at',
    ]
    list_filter = ['status', 'is_featured', 'specialization', 'category']
    search_fields = ['name', 'title', 'specialization', 'bio']
    autocomplete_fields = ['category']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['activate', 'deactivate', 'feature', 'unfeature']

    @admin.action(description=_('Activate selected instructors'))
    def activate(self, request, queryset):
        queryset.update(status=Instructor.ACTIVE)

    @admin.action(description=_('Deactivate selected instructors'))
    def deactivate(self, request, queryset):
        queryset.update(status=Instructor.INACTIVE)

    @admin.action(description=_('Mark as featured'))
    def feature(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description=_('Remove featured flag'))
    def unfeature(self, request, queryset):
        queryset.update(is_featured=False)



admin_site.register(Instructor, InstructorAdmin)
class FaqAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'order', 'status', 'created_at']
    list_filter = ['status', 'category']
    search_fields = ['question', 'answer']
    actions = ['activate', 'deactivate']
    readonly_fields = ['created_at', 'updated_at']

    @admin.action(description=_('Activate selected FAQs'))
    def activate(self, request, queryset):
        queryset.update(status=Faq.ACTIVE)

    @admin.action(description=_('Deactivate selected FAQs'))
    def deactivate(self, request, queryset):
        queryset.update(status=Faq.INACTIVE)



admin_site.register(Faq, FaqAdmin)
class AiInstructionAdmin(admin.ModelAdmin):
    list_display = ['question', 'is_default', 'created_at']
    list_filter = ['is_default']
    search_fields = ['instructions']
    autocomplete_fields = ['question']
    readonly_fields = ['created_at', 'updated_at']



admin_site.register(AiInstruction, AiInstructionAdmin)
class SettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_short', 'updated_at']
    search_fields = ['key']
    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description=_('Value'))
    def value_short(self, obj):
        return (obj.value or '')[:80]

admin_site.register(Setting, SettingAdmin)


class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'certificate_id', 'title', 'student_name', 'related_course',
        'instructor_name', 'issuing_organization', 'issue_date',
        'is_verified', 'is_featured', 'status', 'created_at',
    ]
    list_filter = ['status', 'is_verified', 'is_featured', 'issuing_organization', 'issue_date']
    search_fields = ['certificate_id', 'title', 'student_name', 'related_course', 'instructor_name']
    list_select_related = ['user']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']


admin_site.register(Certificate, CertificateAdmin)
