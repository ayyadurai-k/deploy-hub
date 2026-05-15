from django.urls import path


# Callback views are scoped to a later batch. Routes are reserved here so
# include() resolves at boot and frontend wiring can target stable URLs.
urlpatterns: list = [
    # path("google/start", GoogleStartView.as_view(), name="oauth-google-start"),
    # path("google/callback", GoogleCallbackView.as_view(), name="oauth-google-callback"),
    # path("github/start", GitHubStartView.as_view(), name="oauth-github-start"),
    # path("github/callback", GitHubCallbackView.as_view(), name="oauth-github-callback"),
]
