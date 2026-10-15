"""
Custom Django admin site with RootsExams branding and dashboard stats.
"""
from django.contrib.admin import AdminSite
from django.db.models import Count, Sum


class RootsExamsAdminSite(AdminSite):
    site_header = 'RootsExams Administration'
    site_title = 'RootsExams Admin'
    index_title = 'Dashboard'
    index_template = 'admin/dashboard.html'

    def each_context(self, request):
        context = super().each_context(request)
        context['stats'] = self._get_stats()
        return context

    def _get_stats(self):
        # Local imports to avoid circular imports during app startup
        from apps.users.models import User
        from apps.content.models import Category, Blog, Testimonial
        from apps.exams.models import Question, Exam, ExamTrail
        from apps.packages.models import Package, UserPackage
        from apps.payments.models import PaymentTransaction, Invoice

        revenue = PaymentTransaction.objects.filter(is_success=True).aggregate(
            total=Sum('amount')
        )['total'] or 0

        return {
            'users': User.objects.filter(deleted_at__isnull=True).count(),
            'categories': Category.objects.count(),
            'blogs': Blog.objects.count(),
            'testimonials': Testimonial.objects.count(),
            'questions': Question.objects.count(),
            'exams': Exam.objects.count(),
            'exam_trails': ExamTrail.objects.count(),
            'packages': Package.objects.count(),
            'subscriptions': UserPackage.objects.count(),
            'transactions': PaymentTransaction.objects.filter(is_success=True).count(),
            'invoices': Invoice.objects.count(),
            'revenue': revenue,
        }


admin_site = RootsExamsAdminSite(name='rootsadmin')
