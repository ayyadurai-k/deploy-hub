from datetime import datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from oauth.models import GitHubProfile, SyncStatus
from repositories.models import Repository

from .github_client import GitHubAPIError, iter_user_repos


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    return parse_datetime(value)


def sync_repositories(profile: GitHubProfile) -> int:
    """Pull repos for this profile, upsert into Repository, write status onto the profile.
    Returns the count of repos seen."""
    profile.last_sync_status = SyncStatus.IN_PROGRESS
    profile.last_sync_error = ""
    profile.save(update_fields=["last_sync_status", "last_sync_error", "updated_at"])

    access_token = profile.get_access_token()
    count = 0
    try:
        for raw in iter_user_repos(access_token):
            Repository.objects.update_or_create(
                github_profile=profile,
                github_repo_id=raw["id"],
                defaults={
                    "name": raw.get("name", ""),
                    "full_name": raw.get("full_name", ""),
                    "private": bool(raw.get("private", False)),
                    "default_branch": raw.get("default_branch") or "",
                    "description": raw.get("description") or "",
                    "html_url": raw.get("html_url", ""),
                    "github_created_at": _parse_dt(raw.get("created_at")),
                    "github_pushed_at": _parse_dt(raw.get("pushed_at")),
                },
            )
            count += 1
    except GitHubAPIError as exc:
        profile.last_sync_status = SyncStatus.FAILURE
        profile.last_sync_error = exc.message[:5000]
        profile.last_synced_at = timezone.now()
        profile.save(update_fields=[
            "last_sync_status", "last_sync_error", "last_synced_at", "updated_at",
        ])
        raise

    profile.last_sync_status = SyncStatus.SUCCESS
    profile.last_synced_at = timezone.now()
    profile.last_sync_error = ""
    profile.save(update_fields=[
        "last_sync_status", "last_sync_error", "last_synced_at", "updated_at",
    ])
    return count
