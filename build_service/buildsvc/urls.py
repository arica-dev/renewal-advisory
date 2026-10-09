from django.urls import include, path

# Standalone (manage.py runserver) the service answers at /api/build/...
# Mounted inside the FastAPI app at /api/build, that prefix arrives as
# SCRIPT_NAME and the remaining path is matched by the second pattern.
urlpatterns = [
    path("api/build/", include("renewals.urls")),
    path("", include("renewals.urls")),
]
