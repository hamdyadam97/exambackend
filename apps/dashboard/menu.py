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

SECTION_ICONS = {
    'users': 'fa-users',
    'profiles': 'fa-id-card',
    'otp_requests': 'fa-mobile-alt',
    'reset_tokens': 'fa-key',
    'audit_logs': 'fa-history',
    'categories': 'fa-folder-tree',
    'topics': 'fa-tags',
    'sections': 'fa-layer-group',
    'blogs': 'fa-blog',
    'testimonials': 'fa-star',
    'ai_instructions': 'fa-robot',
    'app_info': 'fa-mobile-screen',
    'contact_messages': 'fa-envelope',
    'questions': 'fa-circle-question',
    'answers': 'fa-list-ol',
    'question_topics': 'fa-link',
    'exam_section_links': 'fa-puzzle-piece',
    'exams': 'fa-file-lines',
    'exam_questions': 'fa-list-check',
    'user_exams': 'fa-user-pen',
    'user_exam_answers': 'fa-check-double',
    'user_exam_trials': 'fa-repeat',
    'exam_trails': 'fa-route',
    'exam_trail_details': 'fa-circle-info',
    'exam_trail_categories': 'fa-sitemap',
    'exam_trail_subcategories': 'fa-diagram-project',
    'exam_trail_subsubcategories': 'fa-network-wired',
    'exam_trail_sections': 'fa-columns',
    'exam_trail_topics': 'fa-hashtag',
    'packages': 'fa-box-open',
    'subscriptions': 'fa-credit-card',
    'discount_codes': 'fa-percent',
    'payment_types': 'fa-wallet',
    'transactions': 'fa-money-bill-transfer',
    'money_logs': 'fa-coins',
    'card_tokens': 'fa-credit-card',
    'invoices': 'fa-file-invoice-dollar',
    'notifications': 'fa-bell',
    'notification_receipts': 'fa-envelope-open-text',
    'support': 'fa-headset',
    'settings': 'fa-sliders',
}

MENU_GROUPS = {
    'dashboard': {
        'label': 'Dashboard',
        'label_ar': 'نظرة عامة',
        'icon': 'fa-chart-pie',
        'sections': [],
    },
    'users': {
        'label': 'Users',
        'label_ar': 'المستخدمين',
        'icon': 'fa-users',
        'sections': ['users', 'profiles', 'otp_requests', 'reset_tokens', 'audit_logs'],
    },
    'content': {
        'label': 'Content',
        'label_ar': 'المحتوى',
        'icon': 'fa-newspaper',
        'sections': ['categories', 'topics', 'sections', 'blogs', 'testimonials', 'ai_instructions', 'app_info', 'contact_messages'],
    },
    'exams': {
        'label': 'Exams',
        'label_ar': 'الاختبارات',
        'icon': 'fa-graduation-cap',
        'sections': [
            'questions', 'answers', 'question_topics', 'exam_section_links',
            'exams', 'exam_questions', 'user_exams', 'user_exam_answers',
            'user_exam_trials', 'exam_trails', 'exam_trail_details',
            'exam_trail_categories', 'exam_trail_subcategories',
            'exam_trail_subsubcategories', 'exam_trail_sections', 'exam_trail_topics',
        ],
    },
    'commerce': {
        'label': 'Commerce',
        'label_ar': 'التجارة',
        'icon': 'fa-cart-shopping',
        'sections': ['packages', 'subscriptions', 'discount_codes'],
    },
    'payments': {
        'label': 'Payments',
        'label_ar': 'المدفوعات',
        'icon': 'fa-money-bill-wave',
        'sections': ['payment_types', 'transactions', 'money_logs', 'card_tokens', 'invoices'],
    },
    'reports': {
        'label': 'Reports',
        'label_ar': 'التقارير',
        'icon': 'fa-chart-line',
        'sections': [],
    },
    'system': {
        'label': 'System',
        'label_ar': 'النظام',
        'icon': 'fa-gears',
        'sections': ['notifications', 'notification_receipts', 'support', 'settings'],
    },
}

SECTION_TO_GROUP = {}
for group_key, group in MENU_GROUPS.items():
    for section in group['sections']:
        SECTION_TO_GROUP[section] = group_key


def get_menu_groups(request):
    """Build grouped menu filtered by the user's view permissions."""
    from apps.dashboard.registry import DASHBOARD_MODELS

    groups = []
    for key, group in MENU_GROUPS.items():
        items = []
        for section in group['sections']:
            config = DASHBOARD_MODELS.get(section)
            if not config:
                continue
            model = config['model']
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            perm = f'{app_label}.view_{model_name}'
            if request.user.has_perm(perm) or request.user.is_superuser:
                items.append({
                    'section': section,
                    'label': config['verbose_name'],
                    'icon': SECTION_ICONS.get(section, 'fa-circle'),
                    'url': f'/admin/{section}/',
                })
        if key == 'dashboard' or items:
            groups.append({
                'key': key,
                'label': group['label'],
                'label_ar': group['label_ar'],
                'icon': group['icon'],
                'items': items,
                'url': '/admin/' if key == 'dashboard' else None,
            })
    return groups
