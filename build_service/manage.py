#!/usr/bin/env python
"""Django entry point for the Renewal Build service.

Local:  python build_service/manage.py runserver 8001
"""
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "buildsvc.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
