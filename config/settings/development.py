"""Development settings for DevTask."""

from .base import *  # noqa: F403

DEBUG = True

# Disable compressed manifest in dev to avoid having to run collectstatic on raw edits
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Internal IPs for debug toolbar if used
INTERNAL_IPS = ["127.0.0.1"]
