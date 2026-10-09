"""Settings for the Renewal Build service (Django + Django REST Framework).

The service is stateless: a packet is read, checked and turned into Clasp API
requests within a request, and nothing is stored until a person approves. So
there is no database configured yet; adding Postgres for saved builds is the
next step (see build_service/README.md).
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent
# Reuse the Renewal Advisor engine (age curve, filings, renewal breakdown).
sys.path.insert(0, str(REPO_ROOT / "src"))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = ["rest_framework", "renewals"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "buildsvc.urls"
WSGI_APPLICATION = "buildsvc.wsgi.application"
DATABASES: dict = {}
USE_TZ = True
TIME_ZONE = "UTC"
APPEND_SLASH = False

# Renewal packets are small; keep uploads bounded.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser",
                               "rest_framework.parsers.MultiPartParser"],
    "COERCE_DECIMAL_TO_STRING": True,
}

PACKETS_DIR = REPO_ROOT / "data" / "renewal_packets"
CLASP_API_VERSION = "2026-04-24"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
