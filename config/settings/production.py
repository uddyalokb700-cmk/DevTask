"""Production settings for DevTask."""

import os

from .base import *  # noqa: F403

DEBUG = False

# Validate secret key (allow build-time dummy key if collecting static during image build)
BUILDING_IMAGE = os.environ.get("BUILDING_IMAGE", "False").lower() in ("true", "1", "yes")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if BUILDING_IMAGE:
        SECRET_KEY = "build-time-dummy-secret-key-for-asset-compilation-only"
    else:
        raise ValueError("DJANGO_SECRET_KEY environment variable must be set in production.")

# Allowed hosts
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS and not BUILDING_IMAGE:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be configured in production.")
elif not ALLOWED_HOSTS and BUILDING_IMAGE:
    ALLOWED_HOSTS = ["localhost"]

# CSRF Trusted Origins (required for HTTPS in Django 4/5)
trusted_origins = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if not trusted_origins:
    trusted_origins = [
        f"https://{h}" for h in ALLOWED_HOSTS if h not in ("*", "localhost", "127.0.0.1")
    ]
CSRF_TRUSTED_ORIGINS = trusted_origins

# Security headers & cookies
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "yes")
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")
CSRF_COOKIE_HTTPONLY = False  # Allows same-origin JavaScript to read standard csrftoken cookie
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HTTP Strict Transport Security
if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Django 5.x Static files storage using WhiteNoise compression & cache manifest
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

