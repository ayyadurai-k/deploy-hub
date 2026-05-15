from django.db import models


class Repository(models.Model):
    github_profile = models.ForeignKey(
        "oauth.GitHubProfile",
        on_delete=models.CASCADE,
        related_name="repositories",
    )
    github_repo_id = models.BigIntegerField()
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=512)
    private = models.BooleanField(default=False)
    default_branch = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    html_url = models.URLField()
    github_created_at = models.DateTimeField(null=True, blank=True)
    github_pushed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["github_profile", "github_repo_id"],
                name="unique_repo_per_github_profile",
            ),
        ]
        ordering = ["-github_pushed_at", "id"]
        verbose_name_plural = "Repositories"

    def __str__(self) -> str:
        return self.full_name
