from core.exceptions import GitHubNotConnected
from oauth.models import GitHubProfile
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Repository
from .serializers import RepositorySerializer
from .services.github_client import GitHubAPIError
from .services.github_sync import sync_repositories


def _require_github_profile(user) -> GitHubProfile:
    try:
        return user.github_profile
    except GitHubProfile.DoesNotExist:
        raise GitHubNotConnected()


class RepositoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = _require_github_profile(self.request.user)
        return Repository.objects.filter(github_profile=profile)

    @action(detail=False, methods=["post"])
    def sync(self, request):
        profile = _require_github_profile(request.user)
        try:
            count = sync_repositories(profile)
        except GitHubAPIError as exc:
            return Response(
                {
                    "error": {
                        "code": "github_api_error",
                        "message": "Failed to fetch repositories from GitHub",
                        "detail": {"upstream_status": exc.status_code},
                    }
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"synced": count, "status": profile.last_sync_status})
