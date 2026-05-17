from django.urls import path

from .views import egress_diag, healthz, readyz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    # Temporary diagnostic — confirms which external hosts the deploy
    # platform allows outbound HTTPS to. Remove once OAuth flow is stable.
    path("diag/egress", egress_diag, name="egress_diag"),
]
