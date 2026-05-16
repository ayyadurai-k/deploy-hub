from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List-only — projects are created via the Django admin for the demo.
    The frontend's 'Deploy to K8S' button is a client-side toast and never
    hits the API."""

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)
