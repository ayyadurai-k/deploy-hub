from django.urls import path

from .views import diag_egress, diag_ping, healthz, readyz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    # Temporary diagnostics — remove once OAuth is working.
    path("diag/ping", diag_ping, name="diag_ping"),
    path("diag/egress", diag_egress, name="diag_egress"),
]
