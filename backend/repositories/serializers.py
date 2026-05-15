from rest_framework import serializers

from .models import Repository


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = [
            "id",
            "github_repo_id",
            "name",
            "full_name",
            "private",
            "default_branch",
            "description",
            "html_url",
            "github_created_at",
            "github_pushed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
