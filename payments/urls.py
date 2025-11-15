from django.urls import path
# from .views import CreateCheckoutSessionView
from . import views

urlpatterns = [
    path('generate-khqr/', views.generate_khqr, name='generate_khqr'),
    path('check-payment/', views.check_payment_status, name='check_payment'),

    path("stripe/create-checkout/", views.create_checkout_session, name="create_checkout_session"),
    # path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("check-payment-stripe/", views.check_payment_status_stripe, name="check_payment_status"),
]
