from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.serializers import UserPublicSerializer
from projects.models import Project, ProjectMembership
from projects.permissions import get_user_project_role


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "user", "role", "joined_at"]
        read_only_fields = ["id", "joined_at"]


class AddMemberSerializer(serializers.Serializer):
    username_or_email = serializers.CharField(required=True)
    role = serializers.ChoiceField(
        choices=[
            (ProjectMembership.Role.MANAGER, "Manager"),
            (ProjectMembership.Role.MEMBER, "Member"),
        ],
        default=ProjectMembership.Role.MEMBER,
    )

    def validate_username_or_email(self, value):
        val = value.strip()
        user = User.objects.filter(username__iexact=val).first() or User.objects.filter(email__iexact=val).first()
        if not user:
            raise serializers.ValidationError(f"No user found with username or email '{val}'.")
        if not user.is_active:
            raise serializers.ValidationError(f"User '{user.username}' is not active.")
        return user


class UpdateMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            (ProjectMembership.Role.MANAGER, "Manager"),
            (ProjectMembership.Role.MEMBER, "Member"),
        ]
    )


class TransferOwnershipSerializer(serializers.Serializer):
    new_owner_id = serializers.IntegerField(required=True)

    def validate_new_owner_id(self, value):
        try:
            user = User.objects.get(pk=value)
            if not user.is_active:
                raise serializers.ValidationError("Cannot transfer ownership to an inactive user.")
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user does not exist.")



from drf_spectacular.utils import extend_schema_field


class ArchiveProjectActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["archive", "unarchive"], default="archive")


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
    members_count = serializers.IntegerField(read_only=True, default=0)
    tasks_count = serializers.IntegerField(read_only=True, default=0)
    completed_tasks_count = serializers.IntegerField(read_only=True, default=0)
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "created_at",
            "updated_at",
            "archived_at",
            "members_count",
            "tasks_count",
            "completed_tasks_count",
            "current_user_role",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "archived_at"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_current_user_role(self, obj):
        request = self.context.get("request")
        if request and request.user:
            return get_user_project_role(obj, request.user)
        return None


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["name", "description"]

    def validate_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Project name cannot be empty.")
        return val


class ProjectUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Project
        fields = ["name", "description"]

    def validate_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Project name cannot be empty.")
        return val



class ProjectDetailSerializer(ProjectSerializer):
    members = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["members"]

    @extend_schema_field(ProjectMembershipSerializer(many=True))
    def get_members(self, obj):
        if hasattr(obj, "prefetched_memberships"):
            memberships = obj.prefetched_memberships
        else:
            memberships = obj.memberships.select_related("user", "user__profile").all()
        return ProjectMembershipSerializer(memberships, many=True).data

