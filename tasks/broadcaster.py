import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("devtask")


def broadcast_project_event(project_id, event_type: str, data: dict):
    """Safely broadcast minimal task events to the project's WebSocket group."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f"project_{project_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "project_message",
                    "event": event_type,
                    "data": data,
                },
            )
    except Exception as exc:
        logger.debug(f"Websocket event broadcast skipped: {exc}")
