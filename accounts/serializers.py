from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["display_name", "bio", "avatar_color"]


from drf_spectacular.utils import extend_schema_field


class UserPublicSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    avatar_color = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "display_name", "avatar_color"]

    @extend_schema_field(serializers.CharField())
    def get_display_name(self, obj) -> str:
        if hasattr(obj, "profile"):
            return obj.profile.get_display_name()
        return obj.get_full_name() or obj.username

    @extend_schema_field(serializers.CharField())
    def get_avatar_color(self, obj) -> str:
        if hasattr(obj, "profile"):
            return obj.profile.avatar_color
        return "#3b82f6"


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    display_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        # Validate against Django password validators
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        display_name = validated_data.get("display_name", "").strip()
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        if display_name:
            user.profile.display_name = display_name
            user.profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)


class UpdateProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="profile.display_name", required=False, allow_blank=True)
    bio = serializers.CharField(source="profile.bio", required=False, allow_blank=True)
    avatar_color = serializers.CharField(source="profile.avatar_color", required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "display_name", "bio", "avatar_color"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        email = validated_data.get("email")
        if email and email != instance.email:
            if User.objects.filter(email__iexact=email).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError({"email": "This email is already in use by another account."})
            instance.email = email.lower()
        instance.save()

        profile = instance.profile
        if "display_name" in profile_data:
            profile.display_name = profile_data["display_name"]
        if "bio" in profile_data:
            profile.bio = profile_data["bio"]
        if "avatar_color" in profile_data:
            profile.avatar_color = profile_data["avatar_color"]
        profile.save()

        return instance
