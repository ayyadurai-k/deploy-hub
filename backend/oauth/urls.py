from django.urls import path

from .views import (
    GitHubCallbackView,
    GitHubStartView,
    GoogleCallbackView,
    GoogleStartView,
)

urlpatterns = [
    path("google/start", GoogleStartView.as_view(), name="oauth-google-start"),
    path("google/callback", GoogleCallbackView.as_view(), name="oauth-google-callback"),
    path("github/start", GitHubStartView.as_view(), name="oauth-github-start"),
    path("github/callback", GitHubCallbackView.as_view(), name="oauth-github-callback"),
]
