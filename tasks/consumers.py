from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from projects.models import Project
from projects.permissions import is_project_member


class ProjectTaskConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time project task updates with authorization checks."""

    async def connect(self):
        self.project_id = str(self.scope["url_route"]["kwargs"]["project_id"])
        self.group_name = f"project_{self.project_id}"
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        has_access = await self.check_user_project_access(user, self.project_id)
        if not has_access:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "event": "connected",
                "data": {"project_id": self.project_id, "message": "Subscribed to project live events."},
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name") and self.channel_layer:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def project_message(self, event):
        """Broadcast minimal task update event to the connected client."""
        await self.send_json(
            {
                "event": event.get("event"),
                "data": event.get("data"),
            }
        )

    @database_sync_to_async
    def check_user_project_access(self, user, project_id) -> bool:
        try:
            project = Project.objects.get(pk=project_id)
            return is_project_member(project, user)
        except Project.DoesNotExist:
            return False
