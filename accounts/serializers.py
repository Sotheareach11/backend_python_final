from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser, Team

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

class TeamSerializer(serializers.ModelSerializer):
    members = serializers.StringRelatedField(many=True, read_only=True)
    member_count = serializers.IntegerField(source='members.count', read_only=True)

    class Meta:
        model = Team
        fields = ['id', 'name', 'members', 'member_count']
