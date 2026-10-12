import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("django.request")


def custom_exception_handler(exc, context):
    """Convert Django core ValidationError and Model errors into DRF 400 Bad Request responses.
    For unhandled exceptions in production, logs error and returns a sanitized JSON 500 without leaking stack traces.
    """
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = DRFValidationError(detail=exc.message_dict)
        elif hasattr(exc, "messages"):
            exc = DRFValidationError(detail=exc.messages)
        else:
            exc = DRFValidationError(detail=str(exc))

    response = exception_handler(exc, context)

    if response is None and not settings.DEBUG:
        logger.exception("Unhandled API Exception: %s", exc)
        return Response(
            {"detail": "A server error occurred. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
