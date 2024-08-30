from rest_framework import serializers
from analysis.models import GaitResult, BodyResult
from rest_framework import serializers

class GaitResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = GaitResult
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class BodyResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyResult
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class GaitResponseSerializer(serializers.Serializer):
    data = GaitResultSerializer(many=True)
    message = serializers.CharField(default="OK")
    status = serializers.IntegerField(default=200)

class BodyResponseSerializer(serializers.Serializer):
    data = BodyResultSerializer(many=True)
    message = serializers.CharField(default="OK")
    status = serializers.IntegerField(default=200)