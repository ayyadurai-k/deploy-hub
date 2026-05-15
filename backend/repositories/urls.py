from rest_framework.routers import DefaultRouter

from .views import RepositoryViewSet


router = DefaultRouter(trailing_slash=False)
router.register(r"", RepositoryViewSet, basename="repository")

urlpatterns = router.urls
