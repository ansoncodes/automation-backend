import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smec.settings")
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@smec.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not password:
    print("DJANGO_SUPERUSER_PASSWORD not set — skipping superuser creation.")
else:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Superuser '{username}' created.")
    else:
        print(f"Superuser '{username}' already exists — skipping.")