from django.contrib import admin

from .models import Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "private",
        "default_branch",
        "github_pushed_at",
        "github_profile",
    ]
    list_filter = ["private"]
    search_fields = ["full_name", "name", "github_profile__user__email"]
    readonly_fields = ["created_at", "updated_at"]
