from rest_framework import serializers

from .models import HuntLog, WantedCriminal


class WantedCriminalSerializer(serializers.ModelSerializer):
    class Meta:
        model = WantedCriminal
        fields = [
            "id", "name", "nickname", "reward",
            "last_known_latitude", "last_known_longitude", "last_known_note",
            "difficulty", "armed", "has_crew", "escape_master",
        ]


class HuntLogSerializer(serializers.ModelSerializer):
    # Accepts and returns the FK as "criminal_id"; an unknown id gives a 400.
    criminal_id = serializers.PrimaryKeyRelatedField(source="criminal", queryset=WantedCriminal.objects.all())

    class Meta:
        model = HuntLog
        fields = ["id", "criminal_id", "success", "notes", "created_at"]
        read_only_fields = ["id", "created_at"]  # created_at is always set by the server


class WantedCriminalDetailSerializer(WantedCriminalSerializer):
    hunts = HuntLogSerializer(many=True, read_only=True)

    class Meta(WantedCriminalSerializer.Meta):
        fields = WantedCriminalSerializer.Meta.fields + ["hunts"]
