from rest_framework import serializers

from analysis.models import UserInfo, UserHist, SessionInfo, SchoolInfo, GaitResult, BodyResult, CodeInfo, Keypoint

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers

class CodeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeInfo
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class SessionInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionInfo
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class SchoolInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolInfo
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInfo
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class UserHistSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserHist
        fields = '__all__'
        read_only_fields = ['id', 'created_dt']

class GaitResultSerializer(serializers.ModelSerializer):
    user_type = serializers.CharField(source='user.user_type', read_only=True)
    student_name = serializers.CharField(source='user.student_name', read_only=True)
    school_name = serializers.CharField(source='school.school_name', read_only=True)

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

class KeypointSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keypoint
        fields = ['body_result', 'x', 'y', 'z', 'visibility', 'presence']


