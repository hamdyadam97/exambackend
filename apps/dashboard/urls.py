from django.urls import path
from apps.dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('questions/create/', views.QuestionCreateView.as_view(), name='question_create'),
    path('questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question_update'),
    path('exams/create/', views.ExamCreateView.as_view(), name='exam_create'),
    path('exams/<int:pk>/edit/', views.ExamUpdateView.as_view(), name='exam_update'),
    path('<str:section>/', views.ModelListView.as_view(), name='list'),
    path('<str:section>/create/', views.ModelCreateView.as_view(), name='create'),
    path('<str:section>/<int:pk>/edit/', views.ModelUpdateView.as_view(), name='update'),
    path('<str:section>/<int:pk>/delete/', views.ModelDeleteView.as_view(), name='delete'),
    path('<str:section>/<int:pk>/archive/', views.ModelArchiveView.as_view(), name='archive'),
    path('<str:section>/<int:pk>/restore/', views.ModelRestoreView.as_view(), name='restore'),
    path('<str:section>/<int:pk>/duplicate/', views.ModelDuplicateView.as_view(), name='duplicate'),
    path('<str:section>/bulk-action/', views.BulkActionView.as_view(), name='bulk_action'),
    path('<str:section>/import/', views.ModelImportView.as_view(), name='import'),
]
