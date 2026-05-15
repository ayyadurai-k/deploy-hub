from django.utils.text import slugify
from rest_framework import serializers

from repositories.models import Repository

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    repository = serializers.PrimaryKeyRelatedField(
        queryset=Repository.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "repository",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]

    def validate_repository(self, value: Repository | None) -> Repository | None:
        if value is None:
            return None
        user = self.context["request"].user
        if value.github_profile.user_id != user.id:
            raise serializers.ValidationError("Repository does not belong to current user")
        return value

    def _allocate_slug(self, user, name: str) -> str:
        base = slugify(name) or "project"
        candidate = base
        i = 2
        existing = set(
            Project.objects.filter(user=user, slug__startswith=base).values_list("slug", flat=True)
        )
        while candidate in existing:
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        validated_data["slug"] = self._allocate_slug(user, validated_data["name"])
        return super().create(validated_data)
