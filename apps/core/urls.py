"""
API URL configuration.
"""
from django.urls import path
from apps.users.views import (
    SignupView, VerifyOtpView, ResendOtpView, CheckVerificationView,
    LoginView, ForgetPasswordView, VerifyOtpForForgetView, ResetPasswordView,
    GetUserInfoView, UpdateUserInfoView, UpdateUserPasswordView, LogoutView,
)
from apps.content.views import (
    LandingView, HomeView, ContactView, CategoriesView, CategoryDetailView,
    SubCategoriesForCategoryView, GetCategoryView, GetSubcategoryView,
    BlogsView, BlogDetailView, BlogCommentView, InstructorsView, TestimonialsView,
    SupportView, ChatView, QuestionBanksView, PaymentTypesView, UserNotificationsView,
    CertificatesPageView, CertificateVerifyView,
)
from apps.exams.views import (
    LegacyExamListView, ExamListView, ExamDetailView, ExamCreateView,
    ExamSubCategoriesView, ExamSubSubCategoriesView, ExamSectionsView,
    ExamTopicsView, ExamRefreshView, ExamStoreView, ExamResetView,
    ExamQuestionsView, ExamQuestionDetailView, ExamCurrentStageView,
    ExamAdvanceStageView, ExamStageView, ExamStoreQuestionAnswerView,
    ExamStoreSingleQuestionAnswerView, ExamOverviewView, ExamFinishView,
    ExamsPageView, ExamDetailPageView,
)
from apps.packages.views import (
    PackageDataView, PackageListView, PackageDetailView, RelatedPackagesView,
    UserSubscriptionView, CheckCouponView,
    SubscribeView, StoreSubscribeView, PackageCalculatePriceView, CoursesView,
    SubCategoryPackagesView,
)
from apps.payments.views import PaymentCallbackView, PaymentStatusView, PaymentInfoView, ConfirmPaymentView

urlpatterns = [
    # Auth
    path('login', LoginView.as_view(), name='login'),
    path('signup', SignupView.as_view(), name='signup'),
    path('verify-otp', VerifyOtpView.as_view(), name='verify-otp'),
    path('resend-otp', ResendOtpView.as_view(), name='resend-otp'),
    path('check-verification', CheckVerificationView.as_view(), name='check-verification'),
    path('forget', ForgetPasswordView.as_view(), name='forget'),
    path('forget-verify-otp', VerifyOtpForForgetView.as_view(), name='forget-verify-otp'),
    path('reset', ResetPasswordView.as_view(), name='reset'),

    # User
    path('get-user-info', GetUserInfoView.as_view(), name='get-user-info'),
    path('update-user-info', UpdateUserInfoView.as_view(), name='update-user-info'),
    path('update-user-password', UpdateUserPasswordView.as_view(), name='update-user-password'),
    path('logout', LogoutView.as_view(), name='logout'),

    # Home & Content
    path('landing/index', LandingView.as_view(), name='landing'),
    path('home', HomeView.as_view(), name='home'),
    path('contact', ContactView.as_view(), name='contact'),
    path('contactus', ContactView.as_view(), name='contactus'),
    path('blogs/index', BlogsView.as_view(), name='blogs-index'),
    path('blogs/<int:pk>', BlogDetailView.as_view(), name='blog-detail'),
    path('blogs/<int:pk>/comments', BlogCommentView.as_view(), name='blog-comments'),
    path('instructors', InstructorsView.as_view(), name='instructors'),
    path('testimonials', TestimonialsView.as_view(), name='testimonials'),
    path('support', SupportView.as_view(), name='support'),
    path('chat', ChatView.as_view(), name='chat'),
    path('question-banks', QuestionBanksView.as_view(), name='question-banks'),
    path('payment-types', PaymentTypesView.as_view(), name='payment-types'),
    path('notifications', UserNotificationsView.as_view(), name='notifications'),

    # Categories
    path('categories', CategoriesView.as_view(), name='categories'),
    path('categories/<int:pk>/subcategories', SubCategoriesForCategoryView.as_view(), name='category-subcategories'),
    path('get-category', GetCategoryView.as_view(), name='get-category'),
    path('get-category/<int:pk>', CategoryDetailView.as_view(), name='get-category-detail'),
    path('get-subcategories/<int:pk>', SubCategoriesForCategoryView.as_view(), name='get-subcategories'),
    path('get-subcategory', GetSubcategoryView.as_view(), name='get-subcategory'),
    path('subcategories/<int:pk>/packages', SubCategoryPackagesView.as_view(), name='subcategory-packages'),

    # Public exams page
    path('exams', ExamsPageView.as_view(), name='exams-page'),
    path('exams/<int:pk>', ExamDetailPageView.as_view(), name='exam-detail-page'),

    # Certificates
    path('certificates', CertificatesPageView.as_view(), name='certificates-page'),
    path('certificates/verify', CertificateVerifyView.as_view(), name='certificate-verify'),

    # Legacy exams
    path('get-exams', LegacyExamListView.as_view(), name='get-exams'),

    # Exam trails
    path('exams/get', ExamListView.as_view(), name='exam-list'),
    path('exams/<int:exam_id>/get', ExamDetailView.as_view(), name='exam-detail'),
    path('exams/create', ExamCreateView.as_view(), name='exam-create'),
    path('exams/subcategories', ExamSubCategoriesView.as_view(), name='exam-subcategories'),
    path('exams/sub-subcategories', ExamSubSubCategoriesView.as_view(), name='exam-sub-subcategories'),
    path('exams/sections', ExamSectionsView.as_view(), name='exam-sections'),
    path('exams/topics', ExamTopicsView.as_view(), name='exam-topics'),
    path('exams/refresh-sections-and-topics', ExamRefreshView.as_view(), name='exam-refresh'),
    path('exams/store', ExamStoreView.as_view(), name='exam-store'),
    path('exams/reset', ExamResetView.as_view(), name='exam-reset'),
    path('exams/get-questions', ExamQuestionsView.as_view(), name='exam-questions'),
    path('exams/<int:question_id>/get-question', ExamQuestionDetailView.as_view(), name='exam-question-detail'),
    path('exams/<int:exam_id>/current-stage', ExamCurrentStageView.as_view(), name='exam-current-stage'),
    path('exams/<int:exam_id>/advance-stage', ExamAdvanceStageView.as_view(), name='exam-advance-stage'),
    path('exams/<int:exam_id>/stage/<int:stage_number>', ExamStageView.as_view(), name='exam-stage'),
    path('exams/<int:exam_id>/store-question-answer', ExamStoreQuestionAnswerView.as_view(), name='exam-store-answers'),
    path('exams/<int:exam_id>/store-single-question-answer', ExamStoreSingleQuestionAnswerView.as_view(), name='exam-store-single-answer'),
    path('exams/<int:exam_id>/overview', ExamOverviewView.as_view(), name='exam-overview'),
    path('exams/<int:exam_id>/finish', ExamFinishView.as_view(), name='exam-finish'),

    # Packages
    path('packages/data', PackageDataView.as_view(), name='package-data'),
    path('packages/index', PackageListView.as_view(), name='package-list'),
    path('courses', CoursesView.as_view(), name='courses'),
    path('packages/<int:pk>/get', PackageDetailView.as_view(), name='package-detail'),
    path('packages/<int:pk>/related', RelatedPackagesView.as_view(), name='package-related'),
    path('packages/user-subscription', UserSubscriptionView.as_view(), name='user-subscription'),
    path('packages/subscribe', SubscribeView.as_view(), name='package-subscribe'),
    path('packages/store-subscribe', StoreSubscribeView.as_view(), name='package-store-subscribe'),
    path('packages/check-coupon', CheckCouponView.as_view(), name='check-coupon'),
    path('packages/calculate-price', PackageCalculatePriceView.as_view(), name='package-calculate-price'),

    # Payments
    path('payment-callback', PaymentCallbackView.as_view(), name='payment-callback'),
    path('package-payment', PaymentStatusView.as_view(), name='package-payment'),
    path('payment/info', PaymentInfoView.as_view(), name='payment-info'),
    path('payment/confirm', ConfirmPaymentView.as_view(), name='payment-confirm'),
]
