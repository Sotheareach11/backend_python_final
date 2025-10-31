from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site
from rest_framework import generics, viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
from .models import CustomUser,Team
from .serializers import RegisterSerializer, ResetPasswordSerializer, TeamSerializer
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
User = get_user_model()


# -----------------------------
# AUTH & REGISTRATION
# -----------------------------
class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        token = RefreshToken.for_user(user).access_token
        # domain = get_current_site(self.request).domain
        verify_url = f"http://127.0.0.1:8000/api/auth/verify/{token}/"
        send_mail(
            "Verify Email",
            f"Click to verify your account: {verify_url}",
            "noreply@taskapp.com",
            [user.email],
        )


class VerifyEmailView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, token):
        try:
            decoded = AccessToken(token)
            user = User.objects.get(id=decoded["user_id"])
            user.is_active = True
            user.is_verified = True
            user.save()
            return Response({"message": "Email verified"})
        except Exception:
            return Response({"error": "Invalid token"}, status=400)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT login serializer with user info in response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise serializers.ValidationError("Account disabled. Contact admin.")

        data.update(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )
        return data


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# -----------------------------
# PASSWORD RESET
# -----------------------------
class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            reset_url = f"http://127.0.0.1:8000/api/auth/reset-password/{uid}/{token}/"

            send_mail(
                "Reset Password",
                f"Reset link: {reset_url}",
                "noreply@taskapp.com",
                [user.email],
            )
            return Response({"message": "Password reset email sent"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request, uidb64, token):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data["password"]

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid user"}, status=status.HTTP_400_BAD_REQUEST
            )

        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response(
                {"message": "Password reset successful"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST
            )


# -----------------------------
# TEAM MANAGEMENT
# -----------------------------
class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        team = self.get_object()
        members = team.members.all().values("id", "username", "email")
        return Response(list(members))

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get("user_id")

        try:
            user = User.objects.get(id=user_id)
            team.members.add(user)

            if user.user_type == 'basic':
                user.user_type = 'subscription'
                user.save()

            return Response({"message": f"{user.username} added to {team.name}."})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get("user_id")

        if user.teams.count() == 0:
            user.user_type = 'basic'
            user.save()

        try:
            user = User.objects.get(id=user_id)
            team.members.remove(user)
            return Response({"message": f"{user.username} removed from {team.name}."})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


# -----------------------------
# USER MANAGEMENT (ADMIN ONLY)
# -----------------------------
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({"message": f"{user.username} disabled."})

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({"message": f"{user.username} enabled."})


# -----------------------------
# AUTHENTICATED USER INFO
# -----------------------------
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_me(request):
    """Return info about the current logged-in user."""
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "user_type": user.user_type,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
        }
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_info(request):
    user = request.user

    # ✅ Automatically downgrade expired subscription
    if user.user_type == "subscription" and user.subscription_end:
        if user.subscription_end < timezone.now():
            user.user_type = "basic"
            user.subscription_end = None
            user.save(update_fields=["user_type", "subscription_end"])

    # ✅ Return user info for Flutter
    user_info = {
        "username": user.username,
        "email": user.email,
        "user_type": user.user_type,
        "subscription_end": (
            user.subscription_end.isoformat() if user.subscription_end else None
        ),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }

    return Response(user_info)