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
