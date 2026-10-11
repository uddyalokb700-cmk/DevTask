import django_filters
from django.db.models import Q
from django.utils import timezone

from tasks.models import Task


class TaskFilter(django_filters.FilterSet):
    project_id = django_filters.UUIDFilter(field_name="project_id")
    status = django_filters.ChoiceFilter(choices=Task.Status.choices)
    priority = django_filters.ChoiceFilter(choices=Task.Priority.choices)
    assignee_id = django_filters.CharFilter(method="filter_assignee")
    search = django_filters.CharFilter(method="filter_search")
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    is_overdue = django_filters.BooleanFilter(method="filter_overdue")

    class Meta:
        model = Task
        fields = ["project_id", "status", "priority", "assignee_id", "search", "due_date_from", "due_date_to"]

    def filter_assignee(self, queryset, name, value):
        if value in ("null", "unassigned", "none"):
            return queryset.filter(assignee__isnull=True)
        try:
            val_int = int(value)
            return queryset.filter(assignee_id=val_int)
        except ValueError:
            return queryset.none()

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))

    def filter_overdue(self, queryset, name, value):
        today = timezone.now().date()
        if value is True:
            return queryset.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
        elif value is False:
            return queryset.exclude(due_date__lt=today, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS])
        return queryset
