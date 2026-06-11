"""
smec/wsgi.py

WSGI config for the SMEC Backend project.

Used by gunicorn in production:
    gunicorn smec.wsgi:application
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smec.settings")

application = get_wsgi_application()
