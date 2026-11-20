from rest_framework import serializers


class HealthSerializer(serializers.Serializer[object]):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    version = serializers.CharField()
    server_time = serializers.DateTimeField()
    epoch_ms = serializers.IntegerField()
    database = serializers.BooleanField()
    cache = serializers.BooleanField()
