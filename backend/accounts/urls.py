from django.urls import path

from .views import LogoutView, MeView, RefreshView

urlpatterns = [
    path("me", MeView.as_view(), name="auth-me"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
]
