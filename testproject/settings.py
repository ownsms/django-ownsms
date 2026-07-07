SECRET_KEY = "test-only"
USE_TZ = True
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.contenttypes", "django.contrib.auth", "ownsms"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "testproject.urls"
