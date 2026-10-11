from django.urls import path

from tasks.views import tasks_view

app_name = "tasks"

urlpatterns = [
    path("tasks/", tasks_view, name="tasks-list"),
]
