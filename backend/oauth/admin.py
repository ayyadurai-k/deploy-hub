from django.contrib import admin

from .models import GitHubProfile, GoogleProfile


@admin.register(GoogleProfile)
class GoogleProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "email", "google_sub", "created_at"]
    search_fields = ["user__email", "email", "google_sub"]
    readonly_fields = [
        "access_token_encrypted",
        "refresh_token_encrypted",
        "created_at",
        "updated_at",
    ]


@admin.register(GitHubProfile)
class GitHubProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "github_login",
        "github_user_id",
        "last_sync_status",
        "last_synced_at",
    ]
    search_fields = ["user__email", "github_login"]
    list_filter = ["last_sync_status"]
    readonly_fields = ["access_token_encrypted", "created_at", "updated_at"]
