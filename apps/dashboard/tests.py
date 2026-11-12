from django.test import TestCase, Client
from django.urls import reverse
from apps.users.models import User
from apps.content.models import Category


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            phone='+962790000001',
            password='admin123',
            email='admin_test@rootsexams.com',
        )
        self.user = User.objects.create_user(
            phone='+962790000002',
            password='user123',
            email='user_test@rootsexams.com',
        )

    def test_dashboard_redirects_anonymous_to_login(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/system-admin/login/', response.url)

    def test_dashboard_loads_for_superuser(self):
        self.client.login(phone='+962790000001', password='admin123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RootsExams')

    def test_removed_exam_sections_are_404_without_error_logs(self):
        self.client.login(phone='+962790000001', password='admin123')
        with self.assertNoLogs('api', level='ERROR'):
            for url in ('/admin/exams/', '/admin/exams/create/', '/admin/user_exams/', '/admin/no-such-section/'):
                self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_list_view_loads(self):
        self.client.login(phone='+962790000001', password='admin123')
        response = self.client.get('/admin/users/')
        self.assertEqual(response.status_code, 200)

    def test_category_create_view_loads(self):
        self.client.login(phone='+962790000001', password='admin123')
        response = self.client.get('/admin/categories/create/')
        self.assertEqual(response.status_code, 200)

    def test_category_create(self):
        self.client.login(phone='+962790000001', password='admin123')
        response = self.client.post('/admin/categories/create/', {
            'name': 'Test Category',
            'level': 1,
            'order': 1,
            'status': 1,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(name='Test Category').exists())

    def test_reports_view_loads(self):
        self.client.login(phone='+962790000001', password='admin123')
        response = self.client.get('/admin/reports/')
        self.assertEqual(response.status_code, 200)


class DashboardLogoutTests(TestCase):
    def test_logout_button_posts_and_logs_out(self):
        admin = User.objects.create_superuser(phone='+962790000009', password='admin123', email='a9@rootsexams.com')
        client = Client()
        client.force_login(admin)
        page = client.get('/admin/').content.decode()
        self.assertIn('method="post" action="/system-admin/logout/"', page)
        self.assertNotIn('href="/system-admin/logout/"', page)
        self.assertIn('/system-admin/password_change/', page)
        self.assertEqual(client.get('/system-admin/password_change/').status_code, 200)
        res = client.post('/system-admin/logout/')
        self.assertIn(res.status_code, (200, 302))
        self.assertEqual(client.get('/admin/').status_code, 302)  # logged out: back to the login page
