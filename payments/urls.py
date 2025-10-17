from django.urls import path
# from .views import CreateCheckoutSessionView
from . import views

urlpatterns = [
    path('generate-khqr/', views.generate_khqr, name='generate_khqr'),
    path('check-payment/', views.check_payment_status, name='check_payment'),
]
