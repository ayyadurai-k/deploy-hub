from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"", ProjectViewSet, basename="project")

urlpatterns = router.urls
