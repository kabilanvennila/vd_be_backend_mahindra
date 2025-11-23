from django.shortcuts import render
from django.contrib.auth import authenticate, get_user_model
from django.http import JsonResponse
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError as PydanticValidationError
from django.db.models import F

from testing.models import Test
from .dto import LoginRequest, SignupRequest
from vd_be.middleware import jwt_authentication
from organisation.models import ProjectEmployee, Project, Vehicle, VehicleSpec
from .serializers import ProjectSerializer, UserSerializer, ProjectEmployeeSerializer, VehicleSpecSerializer

User = get_user_model()

@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
        validated_data = LoginRequest(**data)
        user = authenticate(request, username=validated_data.username, password=validated_data.password)
        if user is not None:
            payload = {
                'user_id': user.id,
                'exp': datetime.now() + timedelta(hours=24),
                'iat': datetime.now()
            }
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
            response = JsonResponse({'token': token}, status=200)
            response.set_cookie('jwt', token, httponly=True)  # Set the token in a cookie
            return response
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status=400)
    except PydanticValidationError as e:
        return JsonResponse({'error': e.errors()}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An error occurred: ' + str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def signup_view(request):
    try:
        data = json.loads(request.body)
        validated_data = SignupRequest(**data)

        # Create the user
        user = User.objects.create_user(username=validated_data.username, email=validated_data.email, password=validated_data.password)

        # Optional fields
        user.phone_number = validated_data.phone_number
        user.address = validated_data.address
        user.height = validated_data.height
        user.weight = validated_data.weight
        user.gender = validated_data.gender
        user.date_of_birth = datetime.strptime(validated_data.date_of_birth, '%Y-%m-%d').date()
        user.profile_picture_url = validated_data.profile_picture_url
        user.save()

        return JsonResponse({'message': 'User created successfully'}, status=201)
    except PydanticValidationError as e:
        return JsonResponse({'message': 'Validation error'}, status=400)
    except Exception as e:
        return JsonResponse({'message': 'Something went wrong'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def user_details_view(request):
    try:
        user = User.get_by_id(request.user_id)
        user_data = UserSerializer(user).data
        return JsonResponse({'user': user_data}, status=200)
    except User.DoesNotExist:
        return JsonResponse({'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'message': 'Something went wrong'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def user_projects_view(request):
    try:
        user = User.get_by_id(request.user_id)
        project_employees = ProjectEmployee.objects.filter(user=user)
        projects_data = ProjectSerializer([pe.project for pe in project_employees], many=True).data
        
        return JsonResponse({'projects': projects_data}, status=200)
    except User.DoesNotExist:
        return JsonResponse({'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'message': 'Something went wrong: ' + str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication   
def project_employees_view(request, project_id):
    try:
        project = Project.get_by_id(project_id)
        project_employees = ProjectEmployee.objects.filter(project=project)
        project_employees_data = ProjectEmployeeSerializer(project_employees, many=True).data
        return JsonResponse({'project_employees': project_employees_data}, status=200)
    except Exception as e:
        return JsonResponse({'message': 'Something went wrong: ' + str(e)}, status=500)
    
@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication   
def vehicle_specs_view(request, vehicle_id):
    try:
        vehicle = Vehicle.get_by_id(vehicle_id)
        vehicle_specs = VehicleSpec.objects.filter(vehicle=vehicle)
        vehicle_specs_data = VehicleSpecSerializer(vehicle_specs, many=True).data
        return JsonResponse({'vehicle_specs': vehicle_specs_data}, status=200)
    except Exception as e:
        return JsonResponse({'message': 'Something went wrong: ' + str(e)}, status=500)