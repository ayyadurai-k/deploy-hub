from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def deploy(self, request, pk=None):
        project = self.get_object()
        # plan.md §14 — placeholder. No persistence. No upstream call.
        return Response(
            {
                "error": {
                    "code": "deploy_not_implemented",
                    "message": "Deployment is not yet supported — coming soon",
                    "detail": {"project_id": project.id, "project_name": project.name},
                }
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
