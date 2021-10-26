from rest_framework import serializers

from constants.tableau_api_constants import SERIALIZABLE_FIELD_NAMES
from database.security_models import ApiKey
from database.tableau_api_models import SummaryStatisticDaily


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = [
            "access_key_id",
            "created_on",
            "has_tableau_api_permissions",
            "is_active",
            "readable_name",
        ]


class SummaryStatisticDailySerializer(serializers.ModelSerializer):
    class Meta:
        model = SummaryStatisticDaily
        fields = SERIALIZABLE_FIELD_NAMES

    participant_id = serializers.SlugRelatedField(
        slug_field="patient_id", source="participant", read_only=True
    )
    study_id = serializers.SerializerMethodField()  # Study object id

    def __init__(self, *args, fields=None, **kwargs):
        """ dynamically modify the subset of fields on instantiation """
        super().__init__(*args, **kwargs)
        if fields is not None:
            for field_name in set(self.fields) - set(fields):
                # is this pop valid? the value is a cached property... this needs to be tested.
                self.fields.pop(field_name)

    def get_study_id(self, obj):
        return obj.participant.study.object_id
