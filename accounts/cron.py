from django.utils import timezone
from accounts.models import CustomUser

def auto_downgrade_users():
    expired = CustomUser.objects.filter(user_type='pro', subscription_end__lt=timezone.now())
    for user in expired:
        user.user_type = 'basic'
        user.save()
