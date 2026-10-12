import datetime
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from projects.models import Project, ProjectMembership
from tasks.models import ActivityLog, Task, TaskComment


class Command(BaseCommand):
    help = "Seeds database with synthetic benchmark data (users, projects, tasks, comments, activity logs)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding synthetic benchmark dataset..."))

        users_data = [
            ("alice", "alice@devtask.local", "Alice Developer", "#3b82f6"),
            ("bob", "bob@devtask.local", "Bob Product Lead", "#10b981"),
            ("charlie", "charlie@devtask.local", "Charlie UI Architect", "#8b5cf6"),
            ("david", "david@devtask.local", "David QA Specialist", "#f59e0b"),
        ]

        created_users = {}
        for username, email, display_name, color in users_data:
            user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
            user.set_password("DevTask123!")
            user.first_name = display_name.split()[0]
            user.last_name = display_name.split()[1] if len(display_name.split()) > 1 else ""
            user.is_active = True
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.display_name = display_name
            profile.avatar_color = color
            profile.save()
            created_users[username] = user

        users_list = list(created_users.values())
        alice = created_users["alice"]
        bob = created_users["bob"]
        charlie = created_users["charlie"]

        # Create 20 projects with mixed ownership and memberships
        projects = []
        for i in range(1, 21):
            if i <= 10:
                owner = alice
                mgr = bob
                mbr = charlie
            elif i <= 15:
                owner = bob
                mgr = alice
                mbr = charlie
            else:
                owner = charlie
                mgr = bob
                mbr = alice

            proj, _ = Project.objects.get_or_create(
                name=f"Benchmark Workspace {i:02d}",
                defaults={
                    "description": f"Automated benchmark test workspace number {i} with high volume tasks.",
                    "owner": owner,
                },
            )
            # Memberships
            ProjectMembership.objects.get_or_create(
                project=proj, user=owner, defaults={"role": ProjectMembership.Role.OWNER}
            )
            ProjectMembership.objects.get_or_create(
                project=proj, user=mgr, defaults={"role": ProjectMembership.Role.MANAGER}
            )
            ProjectMembership.objects.get_or_create(
                project=proj, user=mbr, defaults={"role": ProjectMembership.Role.MEMBER}
            )
            projects.append(proj)

        # Create 300 tasks
        existing_task_count = Task.objects.count()
        tasks_to_create = max(0, 300 - existing_task_count)
        statuses = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE]
        priorities = [Task.Priority.LOW, Task.Priority.MEDIUM, Task.Priority.HIGH, Task.Priority.URGENT]
        now = timezone.now()

        created_tasks = []
        for i in range(tasks_to_create):
            proj = random.choice(projects)
            assignee = random.choice(users_list + [None])
            status = random.choice(statuses)
            priority = random.choice(priorities)
            days_offset = random.randint(-14, 30)
            due_date = (now + datetime.timedelta(days=days_offset)).date() if random.random() > 0.2 else None

            task = Task.objects.create(
                project=proj,
                title=f"Synthetic Task #{existing_task_count + i + 1} - System Module Optimization",
                description="Simulated performance benchmark task item testing pagination, filtering, and joins.",
                status=status,
                priority=priority,
                assignee=assignee,
                due_date=due_date,
                created_by=proj.owner,
                position=float(i + 1),
                completed_at=now if status == Task.Status.DONE else None,
            )
            created_tasks.append(task)

        # Create 120 comments
        all_tasks = list(Task.objects.all()[:200])
        existing_comments = TaskComment.objects.count()
        comments_to_create = max(0, 120 - existing_comments)
        for i in range(comments_to_create):
            task = random.choice(all_tasks)
            author = random.choice(users_list)
            TaskComment.objects.create(
                task=task,
                author=author,
                body=f"Benchmark feedback note #{i + 1}: verified schema and cache invalidation.",
            )

        # Create 150 activity logs
        existing_logs = ActivityLog.objects.count()
        logs_to_create = max(0, 150 - existing_logs)
        actions = [
            ActivityLog.Action.TASK_CREATED,
            ActivityLog.Action.STATUS_CHANGED,
            ActivityLog.Action.PRIORITY_CHANGED,
            ActivityLog.Action.ASSIGNMENT_CHANGED,
        ]
        for i in range(logs_to_create):
            proj = random.choice(projects)
            actor = random.choice(users_list)
            action = random.choice(actions)
            ActivityLog.objects.create(
                project=proj,
                actor=actor,
                action=action,
                metadata={"detail": f"Automated benchmark trace event #{i + 1}"},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Synthetic data ready: {User.objects.count()} users, "
                f"{Project.objects.count()} projects, "
                f"{Task.objects.count()} tasks, "
                f"{TaskComment.objects.count()} comments, "
                f"{ActivityLog.objects.count()} activity logs."
            )
        )
