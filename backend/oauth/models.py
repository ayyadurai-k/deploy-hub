from django.conf import settings
from django.db import models

from .services.token_crypto import decrypt, encrypt


class AbstractOAuthProfile(models.Model):
    access_token_encrypted = models.TextField()
    scopes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def set_access_token(self, plaintext: str) -> None:
        self.access_token_encrypted = encrypt(plaintext)

    def get_access_token(self) -> str:
        return decrypt(self.access_token_encrypted)


class GoogleProfile(AbstractOAuthProfile):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_profile",
    )
    google_sub = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    picture_url = models.URLField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Google profile"

    def set_refresh_token(self, plaintext: str | None) -> None:
        self.refresh_token_encrypted = encrypt(plaintext) if plaintext else ""

    def get_refresh_token(self) -> str | None:
        if not self.refresh_token_encrypted:
            return None
        return decrypt(self.refresh_token_encrypted)

    def __str__(self) -> str:
        return f"GoogleProfile<{self.user.email}>"


class SyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"


class GitHubProfile(AbstractOAuthProfile):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="github_profile",
    )
    github_user_id = models.BigIntegerField(unique=True)
    github_login = models.CharField(max_length=255)
    avatar_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    last_sync_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "GitHub profile"

    def __str__(self) -> str:
        return f"GitHubProfile<{self.user.email}>"
