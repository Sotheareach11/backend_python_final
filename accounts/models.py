from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field is required")
        if not email:
            raise ValueError("The Email field is required")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", "admin")  # ✅ auto-mark admin type

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
        ("admin", "Admin"),
    ]

    email = models.EmailField(max_length=190,unique=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default="basic")
    is_verified = models.BooleanField(default=False)
    subscription_end = models.DateTimeField(null=True, blank=True)

    objects = CustomUserManager()

    def is_subscription_active(self):
        """✅ Check if a user's subscription is currently active."""
        return bool(self.subscription_end and self.subscription_end > timezone.now())

    def __str__(self):
        return self.username



class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password', 'is_active', 'user_type']

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False
        )
        return user

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    members = models.ManyToManyField(CustomUser, related_name='teams', blank=True)

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()
