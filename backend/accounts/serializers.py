from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    has_google = serializers.SerializerMethodField()
    has_github = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "date_joined", "has_google", "has_github"]
        read_only_fields = fields

    def get_has_google(self, obj: User) -> bool:
        return hasattr(obj, "google_profile")

    def get_has_github(self, obj: User) -> bool:
        return hasattr(obj, "github_profile")
