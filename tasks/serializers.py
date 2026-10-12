from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from accounts.serializers import UserPublicSerializer
from tasks.models import ActivityLog, Task, TaskComment


class TaskCommentSerializer(serializers.ModelSerializer):
    author = UserPublicSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "task", "author", "body", "created_at", "updated_at"]
        read_only_fields = ["id", "task", "author", "created_at", "updated_at"]


class TaskCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskComment
        fields = ["body"]

    def validate_body(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Comment body cannot be blank.")
        return val


from drf_spectacular.utils import extend_schema_field


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)
    task_title = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ["id", "project", "task", "task_title", "actor", "action", "metadata", "created_at"]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_task_title(self, obj) -> str:
        if obj.task:
            return obj.task.title
        return obj.metadata.get("task_title", "")


class TaskSerializer(serializers.ModelSerializer):
    created_by = UserPublicSerializer(read_only=True)
    assignee = UserPublicSerializer(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "project_name",
            "title",
            "description",
            "status",
            "priority",
            "created_by",
            "assignee",
            "due_date",
            "position",
            "created_at",
            "updated_at",
            "completed_at",
            "comments_count",
            "is_overdue",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
            "completed_at",
            "comments_count",
            "is_overdue",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_overdue(self, obj) -> bool:
        if obj.due_date and obj.status != Task.Status.DONE:
            return obj.due_date < timezone.now().date()
        return False


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    project_id = serializers.UUIDField(required=False)
    assignee_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Task
        fields = [
            "project_id",
            "title",
            "description",
            "status",
            "priority",
            "assignee_id",
            "due_date",
            "position",
        ]

    def validate_title(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Task title cannot be empty.")
        return val

    def validate_assignee_id(self, value):
        if value is None:
            return None
        try:
            user = User.objects.get(pk=value)
            if not user.is_active:
                raise serializers.ValidationError("Cannot assign task to an inactive user.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")



class TaskReorderSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
    position = serializers.FloatField(required=True)
