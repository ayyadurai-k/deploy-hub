from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "repository",
        "status",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["name", "slug", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["repository"]
