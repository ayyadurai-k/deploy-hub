from django.urls import path

from .views import (
    GitHubCallbackView,
    GitHubLinkStartView,
    GitHubStartView,
    GoogleCallbackView,
    GoogleLinkStartView,
    GoogleStartView,
)

urlpatterns = [
    # login (anonymous browser nav)
    path("google/start", GoogleStartView.as_view(), name="oauth-google-start"),
    path("google/callback", GoogleCallbackView.as_view(), name="oauth-google-callback"),
    path("github/start", GitHubStartView.as_view(), name="oauth-github-start"),
    path("github/callback", GitHubCallbackView.as_view(), name="oauth-github-callback"),
    # link (authenticated XHR, returns authorize_url JSON + sets state cookie)
    path("google/link-start", GoogleLinkStartView.as_view(), name="oauth-google-link-start"),
    path("github/link-start", GitHubLinkStartView.as_view(), name="oauth-github-link-start"),
]
