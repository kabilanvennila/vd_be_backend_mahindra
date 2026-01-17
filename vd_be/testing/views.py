from django.shortcuts import render
from django.http import JsonResponse
from testing.models import Test, TestSpecValue, TestParticipant
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from vd_be.middleware import jwt_authentication
from testing.serializers import TestSerializer, TestSpecValueSerializer, TestParticipantSerializer
import json
from testing.dto import TestDTO, TestSpecUpdateDTO
from organisation.models import Project, User, SpecValue, ProjectEmployee
from django.db import transaction
from pydantic import ValidationError as PydanticValidationError

from .models import Session, Feedback, TestGPSCoordinate, FeedbackAnswer, FeedbackQuestion, TestingBenchmarkParams, CategoryScore, Report
from .serializers import SessionSerializer, FeedbackSerializer, FeedbackQuestionSerializer, FeedbackAnswerSerializer, FeedbackAnswerCreateSerializer
from organisation.models import User, Vehicle, Organisation, VehicleSpec

import whisper
import os
from io import BytesIO
from django.http import HttpResponse
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

model = whisper.load_model("base") 

def calculate_category_scores(test):
    """
    Calculate category scores for a test based on feedback answers and benchmark parameters.
    Returns a dictionary with category scores.
    """
    # Get all feedback answers for this test
    feedback_answers = FeedbackAnswer.objects.filter(test=test).select_related('question')
    
    if not feedback_answers.exists():
        return {}
    
    # Get all benchmark params for the questions in this test
    # Filter by organisation to ensure we get the right benchmark params
    question_ids = [fa.question.id for fa in feedback_answers]
    organisation = test.project.organisation
    
    benchmark_params = TestingBenchmarkParams.objects.filter(
        question_id__in=question_ids,
        organisation=organisation
    ).select_related('question')
    
    # Create a mapping: question_id -> list of (category, weightage)
    question_to_categories = {}
    for bp in benchmark_params:
        question_id = bp.question_id
        if question_id not in question_to_categories:
            question_to_categories[question_id] = []
        question_to_categories[question_id].append({
            'category': bp.category,
            'weightage': bp.weightage
        })
    
    # Create a mapping: question_id -> rating
    question_to_rating = {fa.question.id: fa.rating for fa in feedback_answers}
    
    # Calculate scores per category
    category_scores = {}
    category_details = {}  # Store question-level contributions for debugging
    
    # Initialize all categories to 0
    for bp in benchmark_params:
        if bp.category not in category_scores:
            category_scores[bp.category] = 0.0
            category_details[bp.category] = []
    
    # Calculate contributions for each question
    for fa in feedback_answers:
        question_id = fa.question.id
        rating = fa.rating
        
        # Get all categories this question belongs to
        categories = question_to_categories.get(question_id, [])
        
        for cat_info in categories:
            category = cat_info['category']
            weightage = cat_info['weightage']  # This is a percentage (e.g., 40)
            
            # Calculate contribution: rating * (weightage/100)
            # Example: 7 * (40/100) = 7 * 0.4 = 2.8
            contribution = rating * (weightage / 100.0)
            
            category_scores[category] += contribution
            category_details[category].append({
                'question_id': question_id,
                'question': fa.question.question,
                'rating': rating,
                'weightage': weightage,
                'contribution': round(contribution, 2)
            })
    
    # Store scores in database
    for category, score in category_scores.items():
        CategoryScore.objects.update_or_create(
            test=test,
            category=category,
            defaults={'score': round(score, 2)}
        )
    
    return {
        'scores': {cat: round(score, 2) for cat, score in category_scores.items()},
        'details': category_details
    }

# Create your views here.
@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication   
def get_project_tests_view(request, project_id):
    tests = Test.objects.filter(project=project_id).order_by('-updatedAt')
    tests_data = TestSerializer(tests, many=True).data
    test_spec_values = TestSpecValue.objects.filter(test__in=tests)
    test_spec_values_data = TestSpecValueSerializer(test_spec_values, many=True).data
    test_participants = TestParticipant.objects.filter(test__in=tests)  
    test_participants_data = TestParticipantSerializer(test_participants, many=True).data

    # Create a dictionary to map test IDs to their corresponding test_spec_values
    test_spec_values_dict = {}
    test_participants_dict = {}
    
    for spec_value in test_spec_values_data:
        # TestSpecValueSerializer serializes test as a nested object, so we need to get the id from it
        test_id = spec_value.get('test', {}).get('id') if isinstance(spec_value.get('test'), dict) else spec_value.get('test')
        if test_id is not None:
            if test_id not in test_spec_values_dict:
                test_spec_values_dict[test_id] = []
            test_spec_values_dict[test_id].append(spec_value)
    
    for participant in test_participants_data:
        # TestParticipantSerializer serializes test as just an ID (integer), not a nested object
        test_id = participant.get('test')
        if test_id is not None:
            if test_id not in test_participants_dict:
                test_participants_dict[test_id] = []
            test_participants_dict[test_id].append(participant)
    
    # Append the relevant test_spec_values to each test in tests_data
    for test in tests_data:
        test_id = test.get('id')
        if test_id is not None:
            test['spec_values'] = test_spec_values_dict.get(test_id, [])
            test['participants'] = test_participants_dict.get(test_id, [])
        else:
            test['spec_values'] = []
            test['participants'] = []

    return JsonResponse({'tests': tests_data}, status=200)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
@transaction.atomic
def create_test_view(request, project_id):
    try:
        test_dto = TestDTO(**json.loads(request.body))
        project = Project.get_by_id(project_id) 
        test_data = {
            'project': project,
            'status': 'pending',
            'notes': '',
            'isReviewed': False
        }
        participants_data = test_dto.participants
        spec_values_data = test_dto.spec_values
        test = Test.objects.create(**test_data)

        # Verify if the user is part of the project using ProjectEmployee
        for participant in participants_data:
            user = User.get_by_id(participant.user)
            if not ProjectEmployee.objects.filter(project_id=project_id, user=user).exists():
                return JsonResponse({'error': f'User {user.id} is not part of the project'}, status=403)

            # Create participants and their roles
            TestParticipant.objects.create(test=test, role=participant.role, user=user)

        # Create test spec values
        for spec_value in spec_values_data:
            try:
                spec_value_obj = SpecValue.get_by_id(spec_value.spec)
                TestSpecValue.objects.create(test=test, spec=spec_value_obj, isTestingParam=spec_value.isTestingParam)
            except SpecValue.DoesNotExist:
                return JsonResponse({'error': f'SpecValue with id {spec_value.spec} does not exist'}, status=400)
            except Exception as e:
                return JsonResponse({'error': f'Error creating TestSpecValue for spec {spec_value.spec}: {str(e)}'}, status=400)

        return JsonResponse({'message': 'success', 'id': test.id}, status=201)
    except PydanticValidationError as e:
        return JsonResponse({'error': f'Validation error: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
def update_test_spec_value_view(request, test_id):
    update_dto = TestSpecUpdateDTO(**json.loads(request.body))
    TestSpecValue.objects.filter(test=test_id, spec=update_dto.old_spec_id).update(spec=update_dto.new_spec_id, isTestingParam=update_dto.isTestingParam)
    return JsonResponse({'message': 'success'}, status=200)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
def mark_test_as_reviewed(request, test_id):
    test = Test.objects.get(id=test_id)
    test.isReviewed = True
    test.save()
    return JsonResponse({'message': 'success'}, status=200)

@csrf_exempt
@require_http_methods(["PATCH"])
@jwt_authentication
def update_test_status_view(request, test_id):
    """
    Update the status of a test.
    Expected JSON body:
    {
        "status": "pending" | "yet_to_test" | "in_progress" | "completed" | "failed"
    }
    """
    try:
        # Validate test exists
        test = Test.get_by_id(test_id)
        
        # Parse request body
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if not new_status:
            return JsonResponse({'error': 'Status field is required'}, status=400)
        
        # Validate status is one of the allowed choices
        valid_statuses = [choice[0] for choice in Test.TEST_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({
                'error': f'Invalid status. Allowed values are: {", ".join(valid_statuses)}'
            }, status=400)
        
        # Update test status
        test.status = new_status
        test.save()
        
        # Return updated test data
        serializer = TestSerializer(test)
        return JsonResponse({
            'message': 'Test status updated successfully',
            'test': serializer.data
        }, status=200)
        
    except Test.DoesNotExist:
        return JsonResponse({'error': f'Test with id {test_id} not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
def start_session(request):
    try:
        data = json.loads(request.body)
        driver_id = data.get('driver_id')
        vehicle_id = data.get('vehicle_id')
        test_id = data.get('test_id')  # Optional: link to a test

        if not driver_id or not vehicle_id:
            return JsonResponse({'error': 'Missing driver_id or vehicle_id'}, status=400)

        # Validate driver_id exists
        try:
            driver_id_int = int(driver_id)
            User.get_by_id(driver_id_int)
        except (ValueError, User.DoesNotExist):
            return JsonResponse({'error': 'Invalid driver_id. User does not exist'}, status=400)

        # Validate vehicle_id exists
        try:
            vehicle_id_int = int(vehicle_id)
            Vehicle.get_by_id(vehicle_id_int)
        except (ValueError, Vehicle.DoesNotExist):
            return JsonResponse({'error': 'Invalid vehicle_id. Vehicle does not exist'}, status=400)

        # Validate test_id if provided
        test = None
        if test_id:
            try:
                test_id_int = int(test_id)
                test = Test.get_by_id(test_id_int)
            except (ValueError, Test.DoesNotExist):
                return JsonResponse({'error': 'Invalid test_id. Test does not exist'}, status=400)

        session = Session.objects.create(
            driver_id=driver_id, 
            vehicle_id=vehicle_id,
            test=test
        )
        serializer = SessionSerializer(session)
        return JsonResponse(serializer.data, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
def upload_feedback(request):
    try:
        # For multipart/form-data, get data from POST and files from FILES
        session_id = request.POST.get('session_id')
        audio_file = request.FILES.get('file')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if not session_id or not audio_file:
            return JsonResponse({'error': 'Missing session_id or audio file'}, status=400)

        # Validate session exists
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
        except ValueError:
            return JsonResponse({'error': 'Invalid session_id format'}, status=400)

        # Validate audio file
        allowed_types = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a', 'audio/x-m4a', 'audio/aac']
        max_size = 10 * 1024 * 1024  # 10MB
        
        if audio_file.content_type not in allowed_types:
            return JsonResponse({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=400)
        
        if audio_file.size > max_size:
            return JsonResponse({
                'error': f'File too large. Maximum size: {max_size / (1024*1024)}MB'
            }, status=400)

        # Convert latitude and longitude to float if provided
        latitude_float = None
        longitude_float = None
        
        if latitude is not None:
            try:
                latitude_float = float(latitude)
                if not (-90 <= latitude_float <= 90):
                    return JsonResponse({'error': 'Latitude must be between -90 and 90'}, status=400)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid latitude format'}, status=400)
        
        if longitude is not None:
            try:
                longitude_float = float(longitude)
                if not (-180 <= longitude_float <= 180):
                    return JsonResponse({'error': 'Longitude must be between -180 and 180'}, status=400)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid longitude format'}, status=400)

        # Create feedback
        feedback = Feedback.objects.create(
            session=session,
            audio_file=audio_file,
            latitude=latitude_float,
            longitude=longitude_float
        )

        # Transcription logic
        audio_path = feedback.audio_file.path
        transcription_error = None

        try:
            transcription = model.transcribe(audio_path)
            feedback.transcription_text = transcription['text']
            feedback.save()
        except Exception as e:
            transcription_error = str(e)
            # Log error but don't fail the request - feedback is still created
            print(f"Transcription failed: {e}")

        serializer = FeedbackSerializer(feedback)
        response_data = serializer.data
        
        # Include transcription error in response if it occurred
        if transcription_error:
            response_data['transcription_error'] = transcription_error
            response_data['transcription_warning'] = 'Audio file uploaded but transcription failed'
        
        return JsonResponse(response_data, status=201)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def generate_test_report_pdf(request, test_id):
    """
    Generate a comprehensive PDF report for a test including:
    - Test details
    - Vehicle information
    - Participants
    - Specifications
    - GPS coordinates
    - Audio feedback with transcriptions
    - Structured feedback answers
    - Final report rating
    """
    try:
        # Fetch test and related data
        test = Test.get_by_id(test_id)
        project = test.project
        vehicle = project.vehicle
        organisation = project.organisation
        
        # Fetch all related data
        participants = TestParticipant.objects.filter(test=test).select_related('user')
        test_specs = TestSpecValue.objects.filter(test=test).select_related('spec__spec')
        gps_coordinates = TestGPSCoordinate.objects.filter(test=test).order_by('timestamp')
        sessions = Session.objects.filter(test=test)
        feedbacks = Feedback.objects.filter(session__in=sessions).order_by('timestamp')
        feedback_answers = FeedbackAnswer.objects.filter(test=test).select_related('question', 'question__project', 'question__organisation')
        vehicle_specs = VehicleSpec.objects.filter(vehicle=vehicle).select_related('spec__spec')
        
        # Get category scores for this test (calculate if they don't exist)
        category_scores = CategoryScore.objects.filter(test=test).order_by('category')
        if not category_scores.exists() and feedback_answers.exists():
            # Calculate category scores if they haven't been calculated yet
            calculate_category_scores(test)
            category_scores = CategoryScore.objects.filter(test=test).order_by('category')
        
        # Get all questions for the project
        all_project_questions = FeedbackQuestion.objects.filter(project=project).order_by('createdAt')
        
        # Get benchmark params for questions to get categories
        question_ids = [fa.question.id for fa in feedback_answers] if feedback_answers.exists() else []
        if question_ids:
            benchmark_params = TestingBenchmarkParams.objects.filter(question_id__in=question_ids).select_related('question')
            # Create a mapping of question_id to category and weightage
            question_to_benchmark = {bp.question_id: {'category': bp.category, 'weightage': bp.weightage} for bp in benchmark_params}
        else:
            question_to_benchmark = {}
        
        # Get benchmark params for all project questions
        all_question_ids = [q.id for q in all_project_questions]
        all_benchmark_params = TestingBenchmarkParams.objects.filter(question_id__in=all_question_ids).select_related('question')
        all_question_to_benchmark = {bp.question_id: {'category': bp.category, 'weightage': bp.weightage} for bp in all_benchmark_params}
        
        # Calculate final rating from feedback answers
        final_rating = 0
        if feedback_answers.exists():
            total_weighted_score = 0
            total_weightage = 0
            total_answers = feedback_answers.count()
            simple_avg = sum(fa.rating for fa in feedback_answers) / total_answers if total_answers > 0 else 0
            
            # Calculate weighted average if benchmark params exist
            for fa in feedback_answers:
                question_id = fa.question.id
                benchmark_info = question_to_benchmark.get(question_id)
                if benchmark_info:
                    weightage = benchmark_info['weightage']
                    total_weighted_score += fa.rating * weightage
                    total_weightage += weightage
            
            # Use weighted average if available, otherwise use simple average
            if total_weightage > 0:
                final_rating = round(total_weighted_score / total_weightage)
            else:
                final_rating = round(simple_avg)
        
        # Create or update Report record
        report, created = Report.objects.update_or_create(
            test=test,
            defaults={'final_rating': final_rating}
        )
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=20
        )
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=8
        )
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        normal_style.leading = 14
        
        # Title
        story.append(Paragraph("TEST REPORT", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Test Information Section
        story.append(Paragraph("Test Information", heading_style))
        test_data = [
            ['Test ID:', str(test.id)],
            ['Status:', test.status.upper()],
            ['Reviewed:', 'Yes' if test.isReviewed else 'No'],
            ['Created:', test.createdAt.strftime('%Y-%m-%d %H:%M:%S')],
            ['Updated:', test.updatedAt.strftime('%Y-%m-%d %H:%M:%S')],
        ]
        if test.notes:
            test_data.append(['Notes:', test.notes])
        
        test_table = Table(test_data, colWidths=[2*inch, 4*inch])
        test_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(test_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Project Information Section
        story.append(Paragraph("Project Information", heading_style))
        project_data = [
            ['Project ID:', str(project.id)],
            ['Project Name:', project.name],
            ['Project Code:', project.code],
            ['Parent Code:', project.parent_code],
            ['Stage:', str(project.stage)],
            ['Status:', project.status.upper()],
            ['Created:', project.createdAt.strftime('%Y-%m-%d %H:%M:%S')],
            ['Updated:', project.updatedAt.strftime('%Y-%m-%d %H:%M:%S')],
        ]
        
        project_table = Table(project_data, colWidths=[2*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(project_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Organisation Information
        story.append(Paragraph("Organisation Information", heading_style))
        org_data = [
            ['Organisation:', organisation.name],
            ['Description:', organisation.description or 'N/A'],
        ]
        org_table = Table(org_data, colWidths=[2*inch, 4*inch])
        org_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(org_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Vehicle Information
        story.append(Paragraph("Vehicle Information", heading_style))
        vehicle_data = [
            ['Vehicle ID:', str(vehicle.id)],
            ['Name:', vehicle.name],
            ['Body Number:', vehicle.body_number],
            ['Manufacturer:', vehicle.manufacturer],
            ['Year:', str(vehicle.year)],
        ]
        if vehicle.description:
            vehicle_data.append(['Description:', vehicle.description])
        
        vehicle_table = Table(vehicle_data, colWidths=[2*inch, 4*inch])
        vehicle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(vehicle_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Vehicle Specifications
        if vehicle_specs.exists():
            story.append(Paragraph("Vehicle Specifications", heading_style))
            spec_headers = [['Category', 'Specification', 'Value', 'Type', 'Default']]
            spec_data = []
            for vs in vehicle_specs:
                spec_data.append([
                    vs.spec.spec.category,
                    vs.spec.spec.title,
                    vs.spec.value or 'N/A',
                    vs.spec.value_type,
                    'Yes' if vs.default else 'No'
                ])
            
            spec_table = Table(spec_headers + spec_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 0.8*inch, 0.7*inch])
            spec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(spec_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Participants
        if participants.exists():
            story.append(Paragraph("Test Participants", heading_style))
            part_headers = [['Name', 'Username', 'Email', 'Role']]
            part_data = []
            for tp in participants:
                user = tp.user
                part_data.append([
                    user.full_name or user.username,
                    user.username,
                    user.email or 'N/A',
                    tp.role.capitalize()
                ])
            
            part_table = Table(part_headers + part_data, colWidths=[1.5*inch, 1.5*inch, 2*inch, 1*inch])
            part_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(part_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Test Specifications
        if test_specs.exists():
            story.append(Paragraph("Test Specifications", heading_style))
            test_spec_headers = [['Category', 'Specification', 'Value', 'Testing Parameter']]
            test_spec_data = []
            for ts in test_specs:
                test_spec_data.append([
                    ts.spec.spec.category,
                    ts.spec.spec.title,
                    ts.spec.value or 'N/A',
                    'Yes' if ts.isTestingParam else 'No'
                ])
            
            test_spec_table = Table(test_spec_headers + test_spec_data, colWidths=[1.2*inch, 2*inch, 1.8*inch, 1*inch])
            test_spec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(test_spec_table)
            story.append(Spacer(1, 0.3*inch))
        
        # GPS Coordinates
        if gps_coordinates.exists():
            story.append(Paragraph("GPS Coordinates", heading_style))
            gps_headers = [['Latitude', 'Longitude', 'Timestamp']]
            gps_data = []
            for gps in gps_coordinates:
                gps_data.append([
                    f"{gps.lat:.6f}",
                    f"{gps.lon:.6f}",
                    gps.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            gps_table = Table(gps_headers + gps_data, colWidths=[2*inch, 2*inch, 2*inch])
            gps_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(gps_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Audio Feedback
        if feedbacks.exists():
            story.append(PageBreak())
            story.append(Paragraph("Audio Feedback", heading_style))
            for idx, feedback in enumerate(feedbacks, 1):
                story.append(Paragraph(f"Feedback #{idx}", subheading_style))
                feedback_data = [
                    ['Session ID:', str(feedback.session.id)],
                    ['Timestamp:', feedback.timestamp.strftime('%Y-%m-%d %H:%M:%S')],
                ]
                if feedback.latitude and feedback.longitude:
                    feedback_data.append(['Location:', f"Lat: {feedback.latitude:.6f}, Lon: {feedback.longitude:.6f}"])
                if feedback.transcription_text:
                    feedback_data.append(['Transcription:', feedback.transcription_text[:500] + ('...' if len(feedback.transcription_text) > 500 else '')])
                
                feedback_table = Table(feedback_data, colWidths=[2*inch, 4*inch])
                feedback_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(feedback_table)
                story.append(Spacer(1, 0.2*inch))
        
        # Structured Feedback Questions and Answers
        if feedback_answers.exists():
            story.append(PageBreak())
            story.append(Paragraph("Structured Feedback Questions & Answers", heading_style))
            
            # Group answers by category if available
            answers_by_category = {}
            uncategorized_answers = []
            
            for fa in feedback_answers:
                question_id = fa.question.id
                benchmark_info = question_to_benchmark.get(question_id)
                
                if benchmark_info:
                    category = benchmark_info['category']
                    if category not in answers_by_category:
                        answers_by_category[category] = []
                    answers_by_category[category].append({
                        'answer': fa,
                        'weightage': benchmark_info['weightage']
                    })
                else:
                    uncategorized_answers.append(fa)
            
            # Display categorized answers
            for category, answers_list in sorted(answers_by_category.items()):
                story.append(Paragraph(f"Category: {category.upper()}", subheading_style))
                answer_headers = [['Question ID', 'Question', 'Rating', 'Weightage', 'Comment', 'Answered On']]
                answer_data = []
                
                for item in answers_list:
                    fa = item['answer']
                    weightage = item['weightage']
                    question_text = fa.question.question
                    # Don't truncate question - show full text
                    comment_text = fa.comment if fa.comment else 'N/A'
                    
                    answer_data.append([
                        str(fa.question.id),
                        question_text,
                        str(fa.rating),
                        str(weightage),
                        comment_text,
                        fa.createdAt.strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                # Adjust column widths for better display
                answer_table = Table(answer_headers + answer_data, colWidths=[0.6*inch, 2.2*inch, 0.6*inch, 0.6*inch, 1.5*inch, 1*inch])
                answer_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(answer_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Display uncategorized answers
            if uncategorized_answers:
                story.append(Paragraph("Uncategorized Questions", subheading_style))
                answer_headers = [['Question ID', 'Question', 'Rating', 'Comment', 'Answered On']]
                answer_data = []
                
                for fa in uncategorized_answers:
                    question_text = fa.question.question
                    comment_text = fa.comment if fa.comment else 'N/A'
                    
                    answer_data.append([
                        str(fa.question.id),
                        question_text,
                        str(fa.rating),
                        comment_text,
                        fa.createdAt.strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                answer_table = Table(answer_headers + answer_data, colWidths=[0.8*inch, 2.5*inch, 0.7*inch, 2*inch, 1*inch])
                answer_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(answer_table)
                story.append(Spacer(1, 0.3*inch))
            
            # Summary statistics
            if feedback_answers.exists():
                total_answers = feedback_answers.count()
                avg_rating = sum(fa.rating for fa in feedback_answers) / total_answers if total_answers > 0 else 0
                total_weighted_score = 0
                total_weightage = 0
                
                for fa in feedback_answers:
                    question_id = fa.question.id
                    benchmark_info = question_to_benchmark.get(question_id)
                    if benchmark_info:
                        weightage = benchmark_info['weightage']
                        total_weighted_score += fa.rating * weightage
                        total_weightage += weightage
                
                weighted_avg = total_weighted_score / total_weightage if total_weightage > 0 else 0
                
                story.append(Paragraph("Feedback Summary", subheading_style))
                summary_data = [
                    ['Total Questions Answered:', str(total_answers)],
                    ['Average Rating:', f"{avg_rating:.2f}"],
                ]
                if total_weightage > 0:
                    summary_data.append(['Weighted Average Rating:', f"{weighted_avg:.2f}"])
                    summary_data.append(['Total Weightage:', str(total_weightage)])
                
                summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
        
        # All Project Questions (Answered and Unanswered)
        if all_project_questions.exists():
            story.append(PageBreak())
            story.append(Paragraph("All Project Questions", heading_style))
            story.append(Paragraph("This section lists all feedback questions available for this project, including those that were not answered in this test.", normal_style))
            story.append(Spacer(1, 0.1*inch))
            
            # Get answered question IDs
            answered_question_ids = set([fa.question.id for fa in feedback_answers])
            
            # Group questions by category
            questions_by_category = {}
            uncategorized_questions = []
            
            for question in all_project_questions:
                benchmark_info = all_question_to_benchmark.get(question.id)
                is_answered = question.id in answered_question_ids
                
                if benchmark_info:
                    category = benchmark_info['category']
                    if category not in questions_by_category:
                        questions_by_category[category] = []
                    questions_by_category[category].append({
                        'question': question,
                        'weightage': benchmark_info['weightage'],
                        'answered': is_answered
                    })
                else:
                    uncategorized_questions.append({
                        'question': question,
                        'answered': is_answered
                    })
            
            # Display categorized questions
            for category, questions_list in sorted(questions_by_category.items()):
                story.append(Paragraph(f"Category: {category.upper()}", subheading_style))
                question_headers = [['Question ID', 'Question', 'Weightage', 'Status', 'Created']]
                question_data = []
                
                for item in questions_list:
                    q = item['question']
                    weightage = item['weightage']
                    status = 'Answered' if item['answered'] else 'Not Answered'
                    
                    question_data.append([
                        str(q.id),
                        q.question,
                        str(weightage),
                        status,
                        q.createdAt.strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                question_table = Table(question_headers + question_data, colWidths=[0.8*inch, 3.5*inch, 0.7*inch, 1*inch, 1*inch])
                question_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(question_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Display uncategorized questions
            if uncategorized_questions:
                story.append(Paragraph("Uncategorized Questions", subheading_style))
                question_headers = [['Question ID', 'Question', 'Status', 'Created']]
                question_data = []
                
                for item in uncategorized_questions:
                    q = item['question']
                    status = 'Answered' if item['answered'] else 'Not Answered'
                    
                    question_data.append([
                        str(q.id),
                        q.question,
                        status,
                        q.createdAt.strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                question_table = Table(question_headers + question_data, colWidths=[0.8*inch, 4*inch, 1.2*inch, 1*inch])
                question_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(question_table)
                story.append(Spacer(1, 0.3*inch))
        
        # Category Scores Section
        if category_scores.exists():
            story.append(PageBreak())
            story.append(Paragraph("Category Scores", heading_style))
            story.append(Paragraph("Final calculated scores for each category based on feedback answers and weightages.", normal_style))
            story.append(Spacer(1, 0.1*inch))
            
            score_headers = [['Category', 'Score', 'Last Updated']]
            score_data = []
            
            for cs in category_scores:
                score_data.append([
                    cs.category.capitalize(),
                    f"{cs.score:.2f}",
                    cs.updatedAt.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            score_table = Table(score_headers + score_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(score_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Calculate and display overall average if multiple categories exist
            if category_scores.count() > 1:
                total_score = sum(cs.score for cs in category_scores)
                avg_score = total_score / category_scores.count()
                story.append(Paragraph("Overall Average Score", subheading_style))
                avg_data = [
                    ['Average Score Across All Categories:', f"{avg_score:.2f}"]
                ]
                avg_table = Table(avg_data, colWidths=[3*inch, 3*inch])
                avg_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                story.append(avg_table)
                story.append(Spacer(1, 0.3*inch))
        
        # Final Report Rating
        if report:
            story.append(PageBreak())
            story.append(Paragraph("Final Report", heading_style))
            report_data = [
                ['Final Rating:', str(report.final_rating)],
                ['Report Created:', report.createdAt.strftime('%Y-%m-%d %H:%M:%S')],
            ]
            report_table = Table(report_data, colWidths=[2*inch, 4*inch])
            report_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(report_table)
        
        # Build PDF
        try:
            doc.build(story)
        except Exception as e:
            buffer.close()
            return JsonResponse({'error': f'Error building PDF: {str(e)}'}, status=500)
        
        # Get PDF content
        pdf = buffer.getvalue()
        buffer.close()
        
        # Verify PDF was generated
        if not pdf or len(pdf) == 0:
            return JsonResponse({'error': 'PDF generation failed: empty PDF content'}, status=500)
        
        # Generate filename
        pdf_filename = f"test_report_{test_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Save PDF to Report record
        report.pdf_file.save(
            pdf_filename,
            ContentFile(pdf),
            save=True
        )
        
        # Create HTTP response with proper PDF headers
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
        response['Content-Length'] = str(len(pdf))
        return response
        
    except Test.DoesNotExist:
        return JsonResponse({'error': f'Test with id {test_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error generating PDF: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def get_feedback_questions_view(request, project_id):
    """
    Get all feedback questions for a specific project
    """
    try:
        # Validate project exists
        project = Project.get_by_id(project_id)
        
        # Fetch all questions for this project
        questions = FeedbackQuestion.objects.filter(project=project).order_by('-createdAt')
        questions_data = FeedbackQuestionSerializer(questions, many=True).data
        
        return JsonResponse({'questions': questions_data}, status=200)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
def create_feedback_answer_view(request):
    """
    Create a feedback answer for a test
    Expected JSON body:
    {
        "test": <test_id>,
        "question": <question_id>,
        "rating": <integer>,
        "comment": "<optional string>"
    }
    """
    try:
        data = json.loads(request.body)
        test_id = data.get('test')
        question_id = data.get('question')
        rating = data.get('rating')
        comment = data.get('comment', '')
        
        # Validate required fields
        if not test_id or not question_id or rating is None:
            return JsonResponse({
                'error': 'Missing required fields: test, question, and rating are required'
            }, status=400)
        
        # Validate rating is an integer
        try:
            rating = int(rating)
            if rating < 0:
                return JsonResponse({'error': 'Rating must be a non-negative integer'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Rating must be a valid integer'}, status=400)
        
        # Validate test exists
        try:
            test = Test.get_by_id(test_id)
        except Test.DoesNotExist:
            return JsonResponse({'error': 'Test not found'}, status=404)
        except ValueError:
            return JsonResponse({'error': 'Invalid test_id format'}, status=400)
        
        # Validate question exists
        try:
            question = FeedbackQuestion.objects.get(id=question_id)
        except FeedbackQuestion.DoesNotExist:
            return JsonResponse({'error': 'Question not found'}, status=404)
        except ValueError:
            return JsonResponse({'error': 'Invalid question_id format'}, status=400)
        
        # Check if answer already exists for this test and question
        existing_answer = FeedbackAnswer.objects.filter(test=test, question=question).first()
        if existing_answer:
            # Update existing answer
            existing_answer.rating = rating
            existing_answer.comment = comment
            existing_answer.save()
            
            # Recalculate category scores after update
            calculate_category_scores(test)
            
            serializer = FeedbackAnswerSerializer(existing_answer)
            return JsonResponse(serializer.data, status=200)
        
        # Create new answer
        answer = FeedbackAnswer.objects.create(
            test=test,
            question=question,
            rating=rating,
            comment=comment
        )
        
        # Calculate and store category scores after answer is saved
        calculate_category_scores(test)
        
        serializer = FeedbackAnswerSerializer(answer)
        return JsonResponse(serializer.data, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def get_category_scores_view(request, test_id):
    """
    Get category scores for a test.
    Calculates scores if they don't exist or if answers have changed.
    """
    try:
        # Validate test exists
        test = Test.get_by_id(test_id)
        
        # Always recalculate to ensure accuracy (in case answers or benchmark params changed)
        calculate_category_scores(test)
        
        # Get all category scores for this test
        category_scores = CategoryScore.objects.filter(test=test).order_by('category')
        
        # Format response
        scores_data = {}
        for cs in category_scores:
            scores_data[cs.category] = cs.score
        
        # Get detailed breakdown if needed
        feedback_answers = FeedbackAnswer.objects.filter(test=test).select_related('question')
        question_ids = [fa.question.id for fa in feedback_answers]
        organisation = test.project.organisation
        benchmark_params = TestingBenchmarkParams.objects.filter(
            question_id__in=question_ids,
            organisation=organisation
        ).select_related('question')
        
        # Create detailed breakdown per category
        category_details = {}
        question_to_rating = {fa.question.id: fa.rating for fa in feedback_answers}
        
        for bp in benchmark_params:
            category = bp.category
            question_id = bp.question_id
            weightage = bp.weightage
            rating = question_to_rating.get(question_id, 0)
            
            if category not in category_details:
                category_details[category] = []
            
            contribution = rating * (weightage / 100.0)
            category_details[category].append({
                'question_id': question_id,
                'question': bp.question.question,
                'rating': rating,
                'weightage': weightage,
                'contribution': round(contribution, 2)
            })
        
        return JsonResponse({
            'test_id': test_id,
            'scores': scores_data,
            'details': category_details
        }, status=200)
        
    except Test.DoesNotExist:
        return JsonResponse({'error': f'Test with id {test_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@jwt_authentication
def get_test_voice_feedback_view(request, test_id):
    """
    Get all voice feedback (audio feedback) for a specific test.
    
    Relationship: Test -> Session (one-to-many) -> Feedback (one-to-many)
    Since Feedback doesn't have direct test_id, we traverse through Session:
    1. Find all sessions associated with the test
    2. Find all feedbacks associated with those sessions
    
    Returns all feedback entries with audio files, transcriptions, and metadata.
    """
    try:
        # Validate test exists
        test = Test.get_by_id(test_id)
        
        # Get all feedbacks for sessions linked to this test
        # Using relationship traversal: Feedback -> Session -> Test
        feedbacks = Feedback.objects.filter(
            session__test=test
        ).select_related('session').order_by('timestamp')
        
        if not feedbacks.exists():
            return JsonResponse({
                'test_id': test_id,
                'total_feedbacks': 0,
                'feedbacks': [],
                'message': 'No voice feedbacks found for this test. Sessions may not exist or have no feedbacks yet.'
            }, status=200)
        
        # Serialize feedbacks with request context for building absolute URLs
        serializer = FeedbackSerializer(feedbacks, many=True, context={'request': request})
        feedbacks_data = serializer.data
        
        return JsonResponse({
            'test_id': test_id,
            'total_feedbacks': feedbacks.count(),
            'feedbacks': feedbacks_data
        }, status=200)
        
    except Test.DoesNotExist:
        return JsonResponse({'error': f'Test with id {test_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@jwt_authentication
def session_detail_view(request, session_id):
    """
    Get or update a session by ID.
    GET: Returns session details
    PATCH: Updates session fields (test, driver_id, vehicle_id)
    """
    try:
        session = Session.objects.get(id=session_id)
        
        if request.method == 'GET':
            serializer = SessionSerializer(session)
            return JsonResponse(serializer.data, status=200)
        
        elif request.method == 'PATCH':
            data = json.loads(request.body)
            
            # Update allowed fields
            if 'test_id' in data:
                test_id = data.get('test_id')
                if test_id is not None:
                    try:
                        test = Test.get_by_id(test_id)
                        session.test = test
                    except Test.DoesNotExist:
                        return JsonResponse({'error': f'Test with id {test_id} not found'}, status=404)
                else:
                    session.test = None
            
            if 'driver_id' in data:
                driver_id = data.get('driver_id')
                if driver_id:
                    try:
                        driver_id_int = int(driver_id)
                        User.get_by_id(driver_id_int)
                        session.driver_id = driver_id
                    except (ValueError, User.DoesNotExist):
                        return JsonResponse({'error': 'Invalid driver_id. User does not exist'}, status=400)
            
            if 'vehicle_id' in data:
                vehicle_id = data.get('vehicle_id')
                if vehicle_id:
                    try:
                        vehicle_id_int = int(vehicle_id)
                        Vehicle.get_by_id(vehicle_id_int)
                        session.vehicle_id = vehicle_id
                    except (ValueError, Vehicle.DoesNotExist):
                        return JsonResponse({'error': 'Invalid vehicle_id. Vehicle does not exist'}, status=400)
            
            session.save()
            serializer = SessionSerializer(session)
            return JsonResponse(serializer.data, status=200)
            
    except Session.DoesNotExist:
        return JsonResponse({'error': f'Session with id {session_id} not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)