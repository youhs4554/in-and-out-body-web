from .models import GaitAnalysis, UserInfo, GaitAnalysis, PoseAnalysis
from django.contrib.auth.models import Group
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInfo
        fields = '__all__'

class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']

class GaitAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = GaitAnalysis
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class PoseAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = PoseAnalysis
        fields = '__all__'
        read_only_fields = ['id', 'created_at']