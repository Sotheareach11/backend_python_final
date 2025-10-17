from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, VerifyEmailView, LoginView, ForgotPasswordView, ResetPasswordView, UserViewSet, TeamViewSet,UserViewSet, TeamViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('teams', TeamViewSet, basename='teams')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('login/', LoginView.as_view(), name='login'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<uidb64>/<token>/', ResetPasswordView.as_view(), name='reset-password'),
]

urlpatterns += router.urls
