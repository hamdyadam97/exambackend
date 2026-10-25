from apps.users.models import User, UserProfile, OtpRequest, PasswordResetToken, AuditLog
from apps.content.models import (
    Category, QuestionsTopic, ExamSection, Blog, Testimonial,
    Notification, NotificationReceipt, AppInfo, ContactMessage,
    SupportRequest, AiInstruction, Setting,
)
from apps.exams.models import (
    Question, Answer, QuestionTopic, ExamSectionLink, Exam,
    ExamQuestion, UserExam, UserExamAnswer, UserExamTrial,
    ExamTrail, ExamTrialDetail,
    ExamTrailCategoryLink, ExamTrailSubCategoryLink,
    ExamTrailSubSubCategoryLink, ExamTrailSectionLink, ExamTrailTopicLink,
)
from apps.packages.models import (
    Package, UserPackage, DiscountCode,
)
from apps.payments.models import (
    PaymentType, PaymentTransaction, MoneyLog,
    PaymentCardToken, Invoice,
)
from apps.dashboard.forms import CategoryForm


def _base(model, verbose_name, list_display, search_fields=None, list_filter=None, exclude=None,
          group=None, icon=None, color=None, form_class=None, exportable=False, importable=False,
          archivable=False, duplicatable=False):
    return {
        'model': model,
        'verbose_name': verbose_name,
        'list_display': list_display,
        'search_fields': search_fields or [],
        'list_filter': list_filter or [],
        'exclude': exclude or ['created_at', 'updated_at', 'deleted_at'],
        'group': group,
        'icon': icon,
        'color': color,
        'form_class': form_class,
        'exportable': exportable,
        'importable': importable,
        'archivable': archivable,
        'duplicatable': duplicatable,
    }


DASHBOARD_MODELS = {
    # Users
    'users': _base(
        User, 'Users',
        ['phone', 'full_name', 'email', 'role_type', 'status', 'is_staff', 'date_joined'],
        search_fields=['phone', 'first_name', 'last_name', 'email'],
        list_filter=['role_type', 'status', 'is_staff'],
        exclude=['deleted_at', 'last_login', 'date_joined'],
    ),
    'profiles': _base(
        UserProfile, 'User Profiles',
        ['user', 'specialization', 'governorate', 'profile_completed'],
        search_fields=['user__phone', 'specialization', 'governorate'],
    ),
    'otp_requests': _base(
        OtpRequest, 'OTP Requests',
        ['phone', 'attempts', 'verified', 'expires_at', 'created_at'],
        search_fields=['phone'],
        list_filter=['verified'],
        exclude=['otp_hash', 'created_at', 'updated_at'],
    ),
    'reset_tokens': _base(
        PasswordResetToken, 'Password Reset Tokens',
        ['user', 'used', 'expires_at', 'created_at'],
        search_fields=['user__phone'],
        list_filter=['used'],
        exclude=['token_hash', 'created_at'],
    ),
    'audit_logs': _base(
        AuditLog, 'Audit Logs',
        ['action', 'entity_type', 'entity_id', 'user', 'created_at'],
        search_fields=['action', 'entity_type', 'entity_id', 'user__phone'],
        list_filter=['action', 'entity_type'],
        exclude=['created_at'],
    ),

    # Content
    'categories': _base(
        Category, 'Categories',
        ['name', 'level', 'parent', 'order', 'status', 'is_top'],
        search_fields=['name'],
        list_filter=['status', 'level'],
        exclude=['deleted_at'],
        group='content', icon='fa-folder-tree', color='violet',
        form_class=CategoryForm, exportable=True, importable=True, archivable=True,
    ),
    'topics': _base(
        QuestionsTopic, 'Question Topics',
        ['topic', 'category'],
        search_fields=['topic', 'category__name'],
    ),
    'sections': _base(
        ExamSection, 'Exam Sections',
        ['name', 'category'],
        search_fields=['name', 'category__name'],
        exclude=['deleted_at'],
    ),
    'blogs': _base(
        Blog, 'Blogs',
        ['title', 'category', 'status', 'created_at'],
        search_fields=['title', 'description'],
        list_filter=['status'],
        exclude=['created_at', 'updated_at'],
    ),
    'testimonials': _base(
        Testimonial, 'Testimonials',
        ['name', 'user', 'rating', 'status', 'created_at'],
        search_fields=['name', 'email', 'content'],
        list_filter=['status', 'rating'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'notifications': _base(
        Notification, 'Notifications',
        ['title', 'created_at'],
        search_fields=['title', 'description'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'notification_receipts': _base(
        NotificationReceipt, 'Notification Receipts',
        ['notification', 'user', 'is_read'],
        search_fields=['notification__title', 'user__phone'],
        list_filter=['is_read'],
        exclude=['created_at'],
    ),
    'app_info': _base(
        AppInfo, 'App Info',
        ['ios_version', 'android_version', 'created_at'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'contact_messages': _base(
        ContactMessage, 'Contact Messages',
        ['name', 'email', 'mobile', 'created_at'],
        search_fields=['name', 'email', 'message'],
        exclude=['created_at', 'updated_at'],
    ),
    'support': _base(
        SupportRequest, 'Support Requests',
        ['user', 'question', 'status', 'created_at'],
        search_fields=['user__phone', 'question_text', 'message'],
        list_filter=['status'],
        exclude=['created_at', 'updated_at'],
    ),
    'ai_instructions': _base(
        AiInstruction, 'AI Instructions',
        ['question', 'is_default'],
        search_fields=['instructions'],
        list_filter=['is_default'],
        exclude=['created_at', 'updated_at'],
    ),
    'settings': _base(
        Setting, 'Settings',
        ['key', 'value'],
        search_fields=['key'],
        exclude=['created_at', 'updated_at'],
    ),

    # Exams
    'questions': _base(
        Question, 'Questions',
        ['text_question', 'category', 'difficulty', 'status', 'answer_type'],
        search_fields=['text_question', 'notes'],
        list_filter=['status', 'answer_type', 'difficulty'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'answers': _base(
        Answer, 'Answers',
        ['question', 'answer_option'],
        search_fields=['answer_option', 'question__text_question'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'question_topics': _base(
        QuestionTopic, 'Question Topics',
        ['question', 'topic'],
        search_fields=['question__text_question', 'topic__topic'],
        exclude=['created_at', 'updated_at'],
    ),
    'exam_section_links': _base(
        ExamSectionLink, 'Exam Section Links',
        ['question', 'section'],
        search_fields=['question__text_question', 'section__name'],
        exclude=['created_at', 'updated_at'],
    ),
    'exams': _base(
        Exam, 'Exams',
        ['title', 'category', 'duration_minutes', 'status'],
        search_fields=['title', 'description'],
        list_filter=['status'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'exam_questions': _base(
        ExamQuestion, 'Exam Questions',
        ['exam', 'question', 'order'],
        search_fields=['exam__title', 'question__text_question'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'user_exams': _base(
        UserExam, 'User Exams',
        ['user', 'exam', 'status', 'score'],
        search_fields=['user__phone', 'exam__title'],
        list_filter=['status'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'user_exam_answers': _base(
        UserExamAnswer, 'User Exam Answers',
        ['user', 'exam', 'question', 'answer', 'is_correct'],
        search_fields=['user__phone', 'exam__title', 'question__text_question'],
        list_filter=['is_correct'],
        exclude=['created_at', 'updated_at'],
    ),
    'user_exam_trials': _base(
        UserExamTrial, 'Exam Trials',
        ['user', 'exam', 'date'],
        search_fields=['user__phone', 'exam__title'],
        exclude=['created_at', 'updated_at'],
    ),
    'exam_trails': _base(
        ExamTrail, 'Exam Trails',
        ['title', 'user', 'mode', 'status'],
        search_fields=['title', 'user__phone'],
        list_filter=['mode', 'status'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'exam_trail_details': _base(
        ExamTrialDetail, 'Exam Trial Details',
        ['exam_trail', 'question', 'answer', 'is_correct', 'is_marked'],
        search_fields=['exam_trail__title', 'question__text_question'],
        list_filter=['is_correct', 'is_marked'],
        exclude=['created_at', 'updated_at'],
    ),
    'exam_trail_categories': _base(
        ExamTrailCategoryLink, 'Trail Categories',
        ['exam_trail', 'category'],
        search_fields=['exam_trail__title', 'category__name'],
    ),
    'exam_trail_subcategories': _base(
        ExamTrailSubCategoryLink, 'Trail Sub-categories',
        ['exam_trail', 'sub_category'],
        search_fields=['exam_trail__title', 'sub_category__name'],
    ),
    'exam_trail_subsubcategories': _base(
        ExamTrailSubSubCategoryLink, 'Trail Sub-sub-categories',
        ['exam_trail', 'sub_sub_category'],
        search_fields=['exam_trail__title', 'sub_sub_category__name'],
    ),
    'exam_trail_sections': _base(
        ExamTrailSectionLink, 'Trail Sections',
        ['exam_trail', 'section'],
        search_fields=['exam_trail__title', 'section__name'],
    ),
    'exam_trail_topics': _base(
        ExamTrailTopicLink, 'Trail Topics',
        ['exam_trail', 'topic'],
        search_fields=['exam_trail__title', 'topic__topic'],
    ),

    # Packages
    'packages': _base(
        Package, 'Packages',
        ['name', 'category', 'price', 'status', 'is_trial'],
        search_fields=['name'],
        list_filter=['status', 'is_trial'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'subscriptions': _base(
        UserPackage, 'Subscriptions',
        ['user', 'package', 'start_date', 'end_date', 'subscription_status'],
        search_fields=['user__phone', 'package__name'],
        list_filter=['subscription_status'],
        exclude=['created_at', 'updated_at', 'deleted_at'],
    ),
    'discount_codes': _base(
        DiscountCode, 'Discount Codes',
        ['code', 'marketer', 'type', 'status', 'used_count', 'quantity'],
        search_fields=['code', 'marketer'],
        list_filter=['type', 'status'],
        exclude=['created_at', 'updated_at'],
    ),

    # Payments
    'payment_types': _base(
        PaymentType, 'Payment Types',
        ['name', 'status'],
        search_fields=['name'],
        list_filter=['status'],
        exclude=['created_at', 'updated_at'],
    ),
    'transactions': _base(
        PaymentTransaction, 'Transactions',
        ['user', 'package', 'amount', 'currency', 'is_success'],
        search_fields=['user__phone', 'payment_id'],
        list_filter=['is_success', 'currency'],
        exclude=['created_at', 'updated_at'],
    ),
    'money_logs': _base(
        MoneyLog, 'Money Logs',
        ['user', 'platform', 'item', 'payment_id', 'status'],
        search_fields=['user__phone', 'payment_id'],
        list_filter=['platform', 'status'],
        exclude=['created_at', 'updated_at'],
    ),
    'card_tokens': _base(
        PaymentCardToken, 'Card Tokens',
        ['user', 'last4', 'brand', 'is_active'],
        search_fields=['user__phone', 'last4'],
        list_filter=['is_active', 'brand'],
        exclude=['token', 'created_at', 'updated_at'],
    ),
    'invoices': _base(
        Invoice, 'Invoices',
        ['invoice_number', 'user', 'total_amount', 'status', 'sent_to_accounting'],
        search_fields=['invoice_number', 'user__phone'],
        list_filter=['status', 'sent_to_accounting'],
        exclude=['created_at', 'updated_at'],
    ),
}


def get_config(section):
    return DASHBOARD_MODELS.get(section)
