from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=User)
def send_verification_email(sender, instance, created, **kwargs):
    if not created:
        return

    # Superusers skip verification and activate immediately
    if instance.is_superuser:
        instance.is_active = True
        if hasattr(instance, 'is_verified'):
            instance.is_verified = True
        instance.save(update_fields=['is_active'] + (['is_verified'] if hasattr(instance, 'is_verified') else []))
        return

    # Send verification email for normal users
    token = RefreshToken.for_user(instance).access_token
    verify_url = f"http://127.0.0.1:8000/api/auth/verify/{token}/"
    subject = "Verify your email"
    message = (
        f"Hi {instance.username},\n\n"
        f"Please verify your account by clicking this link:\n{verify_url}\n\nThank you!"
    )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@taskapp.com"),
        [instance.email],
    )
