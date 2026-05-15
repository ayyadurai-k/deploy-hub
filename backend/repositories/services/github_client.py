from collections.abc import Iterator
from typing import Any

import requests
from django.conf import settings

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"GitHub API {status_code}: {message}")
        self.status_code = status_code
        self.message = message


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repo-manage-backend",
    }


def fetch_user(access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{GITHUB_API_BASE}/user",
        headers=_headers(access_token),
        timeout=10,
    )
    if response.status_code >= 400:
        raise GitHubAPIError(response.status_code, response.text)
    return response.json()


def fetch_primary_email(access_token: str) -> str | None:
    response = requests.get(
        f"{GITHUB_API_BASE}/user/emails",
        headers=_headers(access_token),
        timeout=10,
    )
    if response.status_code >= 400:
        return None
    for entry in response.json():
        if entry.get("primary") and entry.get("verified"):
            return entry.get("email")
    return None


def iter_user_repos(access_token: str) -> Iterator[dict[str, Any]]:
    """Paginate /user/repos, bounded by settings.GITHUB_SYNC."""
    per_page = settings.GITHUB_SYNC["PER_PAGE"]
    max_pages = settings.GITHUB_SYNC["MAX_PAGES"]
    for page in range(1, max_pages + 1):
        response = requests.get(
            f"{GITHUB_API_BASE}/user/repos",
            headers=_headers(access_token),
            params={
                "per_page": per_page,
                "page": page,
                "sort": "pushed",
                "direction": "desc",
                "affiliation": "owner,collaborator,organization_member",
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise GitHubAPIError(response.status_code, response.text)
        batch = response.json()
        if not batch:
            return
        yield from batch
        if len(batch) < per_page:
            return
