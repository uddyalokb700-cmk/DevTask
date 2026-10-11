import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from projects.models import Project, ProjectMembership
from tasks.models import ActivityLog, Task, TaskComment


class Command(BaseCommand):
    help = "Seeds database with demo users, projects, tasks, comments, and activity logs."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding DevTask demo data..."))

        # 1. Superuser
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@devtask.local", "is_staff": True, "is_superuser": True},
        )
        admin.set_password("AdminPass123!")
        admin.save()
        admin.profile.display_name = "System Admin"
        admin.profile.save()

        # 2. Regular Team Members
        users_data = [
            ("alice", "alice@devtask.local", "Alice Developer", "#3b82f6"),
            ("bob", "bob@devtask.local", "Bob Product Lead", "#10b981"),
            ("charlie", "charlie@devtask.local", "Charlie UI Architect", "#8b5cf6"),
            ("david", "david@devtask.local", "David QA Specialist", "#f59e0b"),
        ]

        created_users = {}
        for username, email, display_name, color in users_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            user.set_password("DevTask123!")
            user.first_name = display_name.split()[0]
            user.last_name = display_name.split()[1] if len(display_name.split()) > 1 else ""
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.display_name = display_name
            profile.avatar_color = color
            profile.save()
            created_users[username] = user

        alice = created_users["alice"]
        bob = created_users["bob"]
        charlie = created_users["charlie"]
        david = created_users["david"]

        # 3. Demo Projects
        # Project 1: DevTask Core Engine (Owner: Alice)
        proj1, created = Project.objects.get_or_create(
            name="DevTask Core Platform",
            defaults={
                "description": "High-performance enterprise project management backend and web interface.",
                "owner": alice,
            },
        )
        if not created:
            proj1.owner = alice
            proj1.save()

        # Memberships for Proj1
        ProjectMembership.objects.get_or_create(
            project=proj1, user=alice, defaults={"role": ProjectMembership.Role.OWNER}
        )
        ProjectMembership.objects.get_or_create(
            project=proj1, user=bob, defaults={"role": ProjectMembership.Role.MANAGER}
        )
        ProjectMembership.objects.get_or_create(
            project=proj1, user=charlie, defaults={"role": ProjectMembership.Role.MEMBER}
        )
        ProjectMembership.objects.get_or_create(
            project=proj1, user=david, defaults={"role": ProjectMembership.Role.MEMBER}
        )

        # Project 2: Mobile Client MVP (Owner: Bob)
        proj2, created = Project.objects.get_or_create(
            name="Mobile Client MVP",
            defaults={
                "description": "Cross-platform mobile client for DevTask notifications and task updates.",
                "owner": bob,
            },
        )
        if not created:
            proj2.owner = bob
            proj2.save()

        ProjectMembership.objects.get_or_create(
            project=proj2, user=bob, defaults={"role": ProjectMembership.Role.OWNER}
        )
        ProjectMembership.objects.get_or_create(
            project=proj2, user=alice, defaults={"role": ProjectMembership.Role.MEMBER}
        )
        ProjectMembership.objects.get_or_create(
            project=proj2, user=charlie, defaults={"role": ProjectMembership.Role.MEMBER}
        )

        # 4. Realistic Tasks for Proj1
        today = timezone.now().date()
        tasks_spec = [
            # TODO
            {
                "title": "Implement PostgreSQL connection pooling & health probe",
                "description": "Configure resilient db connection parameters and verify failover handling.",
                "status": Task.Status.TODO,
                "priority": Task.Priority.HIGH,
                "created_by": alice,
                "assignee": alice,
                "due_date": today + datetime.timedelta(days=3),
                "position": 1.0,
            },
            {
                "title": "Add role-based audit logging for project ownership transfer",
                "description": "Ensure every ownership transition generates an immutable audit record.",
                "status": Task.Status.TODO,
                "priority": Task.Priority.URGENT,
                "created_by": bob,
                "assignee": bob,
                "due_date": today + datetime.timedelta(days=1),
                "position": 2.0,
            },
            {
                "title": "Refine dark mode typography tokens for high-DPI displays",
                "description": "Audit contrast ratios across cards, modal backdrops, and badge chips.",
                "status": Task.Status.TODO,
                "priority": Task.Priority.LOW,
                "created_by": charlie,
                "assignee": charlie,
                "due_date": today + datetime.timedelta(days=7),
                "position": 3.0,
            },
            # IN_PROGRESS
            {
                "title": "Build interactive drag-and-drop Kanban board",
                "description": "Support smooth HTML5 drag events, keyboard accessible movement, and optimistic backend sync.",
                "status": Task.Status.IN_PROGRESS,
                "priority": Task.Priority.URGENT,
                "created_by": alice,
                "assignee": alice,
                "due_date": today + datetime.timedelta(days=2),
                "position": 1.0,
            },
            {
                "title": "Write automated query count regression tests",
                "description": "Prevent N+1 query regressions across project listing and task serializer endpoints.",
                "status": Task.Status.IN_PROGRESS,
                "priority": Task.Priority.HIGH,
                "created_by": alice,
                "assignee": david,
                "due_date": today + datetime.timedelta(days=4),
                "position": 2.0,
            },
            # DONE
            {
                "title": "Design normalized database schema & composite indexes",
                "description": "Implemented UUID primary keys, composite indexes on (project, status), and foreign key constraints.",
                "status": Task.Status.DONE,
                "priority": Task.Priority.HIGH,
                "created_by": alice,
                "assignee": alice,
                "due_date": today - datetime.timedelta(days=2),
                "position": 1.0,
            },
            {
                "title": "Configure OpenAPI drf-spectacular schema generation",
                "description": "Exported interactive Swagger UI and schema validation endpoints at /api/docs/.",
                "status": Task.Status.DONE,
                "priority": Task.Priority.MEDIUM,
                "created_by": bob,
                "assignee": bob,
                "due_date": today - datetime.timedelta(days=1),
                "position": 2.0,
            },
        ]

        for spec in tasks_spec:
            task, created = Task.objects.get_or_create(
                project=proj1,
                title=spec["title"],
                defaults={
                    "description": spec["description"],
                    "status": spec["status"],
                    "priority": spec["priority"],
                    "created_by": spec["created_by"],
                    "assignee": spec["assignee"],
                    "due_date": spec["due_date"],
                    "position": spec["position"],
                },
            )
            if created:
                # Add sample comment
                TaskComment.objects.create(
                    task=task,
                    author=bob if spec["assignee"] != bob else alice,
                    body="Looks aligned with our milestone milestones. Let us maintain high test coverage.",
                )
                # Add ActivityLog
                ActivityLog.objects.create(
                    project=proj1,
                    task=task,
                    actor=spec["created_by"],
                    action=ActivityLog.Action.TASK_CREATED,
                    metadata={"title": task.title, "status": task.status, "priority": task.priority},
                )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write(
            self.style.SUCCESS(
                "Users created:\n"
                "  - admin (password: AdminPass123!)\n"
                "  - alice (password: DevTask123!)\n"
                "  - bob (password: DevTask123!)\n"
                "  - charlie (password: DevTask123!)\n"
                "  - david (password: DevTask123!)"
            )
        )
