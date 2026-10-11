from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Convert Django core ValidationError and Model errors into DRF 400 Bad Request responses."""
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = DRFValidationError(detail=exc.message_dict)
        elif hasattr(exc, "messages"):
            exc = DRFValidationError(detail=exc.messages)
        else:
            exc = DRFValidationError(detail=str(exc))

    return exception_handler(exc, context)
