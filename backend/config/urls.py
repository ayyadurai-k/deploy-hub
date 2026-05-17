from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponseNotFound
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache

api_v1 = [
    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("oauth/", include("oauth.urls")),
    path("repositories/", include("repositories.urls")),
]


@never_cache
def spa_fallback(_request):
    """Serve the Vite-built index.html for any client-side route (e.g.
    /auth/complete, /login) that wasn't matched by an API/admin URL or
    by a static file. Only used in the single-container Docker deploy —
    under nginx on Lightsail, nginx's `try_files … /index.html` handles
    this before Django ever sees the request."""
    index = Path(getattr(settings, "WHITENOISE_ROOT", "")) / "index.html"
    if not index.is_file():
        return HttpResponseNotFound("SPA build not found")
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    # Catch-all — must be last. Excludes api/, admin/, static/, assets/
    # so those keep their normal handlers (WhiteNoise serves /static and
    # /assets via middleware before URL resolution).
    re_path(r"^(?!api/|admin/|static/|assets/).*$", spa_fallback),
]
