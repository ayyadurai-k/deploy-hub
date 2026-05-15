from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("oauth/", include("oauth.urls")),
    path("repositories/", include("repositories.urls")),
    path("projects/", include("projects.urls")),
]


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
