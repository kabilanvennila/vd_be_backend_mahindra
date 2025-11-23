from rest_framework import serializers
from django.contrib.auth import get_user_model
from organisation.models import Organisation, ProjectEmployee, Project, Spec, SpecValue, Vehicle, VehicleSpec

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'full_name', 'email', 'phone_number', 'address', 'height', 'weight', 'gender', 'date_of_birth', 'profile_picture_url', 'organisation']

class UserLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name']

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'name', 'description', 'image_url', 'body_number', 'manufacturer', 'year']

class ProjectSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer()

    class Meta:
        model = Project
        fields = ['id', 'name', 'code', 'parent_code', 'status', 'stage', 'vehicle']
        
class ProjectEmployeeSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer()
    class Meta:
        model = ProjectEmployee
        fields = ['user', 'role']

class SpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = Spec
        fields = ['category', 'title']
        
class SpecValueSerializer(serializers.ModelSerializer):
    spec = SpecSerializer()
    class Meta:
        model = SpecValue
        fields = ['spec', 'id', 'value', 'value_type']

class VehicleSpecSerializer(serializers.ModelSerializer):
    spec = SpecValueSerializer()
    class Meta:
        model = VehicleSpec
        fields = ['spec', 'default']

class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = '__all__'


    