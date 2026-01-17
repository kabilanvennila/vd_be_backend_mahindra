from rest_framework import serializers
from django.contrib.auth import get_user_model
from organisation.models import Organisation, ProjectEmployee, Project, Spec, SpecValue, Vehicle, VehicleSpec

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class UserLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer()

    class Meta:
        model = Project
        fields = '__all__'
        
class ProjectEmployeeSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer()
    class Meta:
        model = ProjectEmployee
        fields = '__all__'

class SpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = Spec
        fields = '__all__'
        
class SpecValueSerializer(serializers.ModelSerializer):
    spec = SpecSerializer()
    class Meta:
        model = SpecValue
        fields = '__all__'

class VehicleSpecSerializer(serializers.ModelSerializer):
    spec = SpecValueSerializer()
    class Meta:
        model = VehicleSpec
        fields = '__all__'

class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = '__all__'


    