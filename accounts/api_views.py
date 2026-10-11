from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from accounts.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
    UserPublicSerializer,
)


class RegisterAPIView(APIView):
    """Register a new user account with validated credentials."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: UserPublicSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Automatically log user in
        login(request, user)
        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    """Authenticate with username and password, creating a secure HTTP session."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @method_decorator(ensure_csrf_cookie)
    @extend_schema(
        request=LoginSerializer,
        responses={
            200: UserPublicSerializer,
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            # Try case-insensitive lookup
            from django.contrib.auth.models import User

            try:
                matched = User.objects.get(username__iexact=username)
                user = authenticate(request, username=matched.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        return Response(UserPublicSerializer(user).data, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    """Log out the current user and invalidate the session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Successfully logged out")})
    def post(self, request):
        logout(request)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class CurrentUserAPIView(APIView):
    """Retrieve or update the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserPublicSerializer})
    def get(self, request):
        return Response(UserPublicSerializer(request.user).data)

    @extend_schema(
        request=UpdateProfileSerializer,
        responses={200: UserPublicSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserPublicSerializer(user).data)
