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

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Session, Feedback, TestGPSCoordinate, FeedbackAnswer, Report
from .serializers import SessionSerializer, FeedbackSerializer
from vd_be.middleware import jwt_authentication
from organisation.models import User, Vehicle, Organisation, VehicleSpec

import whisper
import os
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

model = whisper.load_model("base") 

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
        test_id = spec_value['test']
        if test_id not in test_spec_values_dict:
            test_spec_values_dict[test_id] = []
        test_spec_values_dict[test_id].append(spec_value)
    
    for participant in test_participants_data:
        test_id = participant['test']
        if test_id not in test_participants_dict:
            test_participants_dict[test_id] = []
        test_participants_dict[test_id].append(participant)
    
    # Append the relevant test_spec_values to each test in tests_data
    for test in tests_data:
        test_id = test['id']
        test['spec_values'] = test_spec_values_dict.get(test_id, [])
        test['participants'] = test_participants_dict.get(test_id, [])

    return JsonResponse({'tests': tests_data}, status=200)

@csrf_exempt
@require_http_methods(["POST"])
@jwt_authentication
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
            TestSpecValue.objects.create(test=test, spec=SpecValue.get_by_id(spec_value.spec), isTestingParam=spec_value.isTestingParam)

        return JsonResponse({'message': 'success', 'id': test.id}, status=201)
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


@api_view(['POST'])
@jwt_authentication
def start_session(request):
    driver_id = request.data.get('driver_id')
    vehicle_id = request.data.get('vehicle_id')
    test_id = request.data.get('test_id')  # Optional: link to a test

    if not driver_id or not vehicle_id:
        return Response({'error': 'Missing driver_id or vehicle_id'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate driver_id exists
    try:
        driver_id_int = int(driver_id)
        User.get_by_id(driver_id_int)
    except (ValueError, User.DoesNotExist):
        return Response({'error': 'Invalid driver_id. User does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate vehicle_id exists
    try:
        vehicle_id_int = int(vehicle_id)
        Vehicle.get_by_id(vehicle_id_int)
    except (ValueError, Vehicle.DoesNotExist):
        return Response({'error': 'Invalid vehicle_id. Vehicle does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate test_id if provided
    test = None
    if test_id:
        try:
            test_id_int = int(test_id)
            test = Test.get_by_id(test_id_int)
        except (ValueError, Test.DoesNotExist):
            return Response({'error': 'Invalid test_id. Test does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    session = Session.objects.create(
        driver_id=driver_id, 
        vehicle_id=vehicle_id,
        test=test
    )
    serializer = SessionSerializer(session)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@jwt_authentication
def upload_feedback(request):
    session_id = request.data.get('session_id')
    audio_file = request.FILES.get('file')
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')

    if not session_id or not audio_file:
        return Response({'error': 'Missing session_id or audio file'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate session exists
    try:
        session = Session.objects.get(id=session_id)
    except Session.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({'error': 'Invalid session_id format'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate audio file
    allowed_types = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a', 'audio/x-m4a', 'audio/aac']
    max_size = 10 * 1024 * 1024  # 10MB
    
    if audio_file.content_type not in allowed_types:
        return Response({
            'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if audio_file.size > max_size:
        return Response({
            'error': f'File too large. Maximum size: {max_size / (1024*1024)}MB'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Convert latitude and longitude to float if provided
    latitude_float = None
    longitude_float = None
    
    if latitude is not None:
        try:
            latitude_float = float(latitude)
            if not (-90 <= latitude_float <= 90):
                return Response({'error': 'Latitude must be between -90 and 90'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid latitude format'}, status=status.HTTP_400_BAD_REQUEST)
    
    if longitude is not None:
        try:
            longitude_float = float(longitude)
            if not (-180 <= longitude_float <= 180):
                return Response({'error': 'Longitude must be between -180 and 180'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid longitude format'}, status=status.HTTP_400_BAD_REQUEST)

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
    
    return Response(response_data, status=status.HTTP_201_CREATED)


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
        feedback_answers = FeedbackAnswer.objects.filter(test=test).select_related('question')
        report = Report.objects.filter(test=test).first()
        vehicle_specs = VehicleSpec.objects.filter(vehicle=vehicle).select_related('spec__spec')
        
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
            ['Project:', project.name],
            ['Project Code:', project.code],
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
        
        # Structured Feedback Answers
        if feedback_answers.exists():
            story.append(PageBreak())
            story.append(Paragraph("Structured Feedback", heading_style))
            answer_headers = [['Category', 'Question', 'Rating', 'Comment']]
            answer_data = []
            for fa in feedback_answers:
                answer_data.append([
                    fa.question.category,
                    fa.question.question[:50] + ('...' if len(fa.question.question) > 50 else ''),
                    str(fa.rating),
                    fa.comment[:100] + ('...' if len(fa.comment) > 100 else '') if fa.comment else 'N/A'
                ])
            
            answer_table = Table(answer_headers + answer_data, colWidths=[1*inch, 2.5*inch, 0.8*inch, 1.7*inch])
            answer_table.setStyle(TableStyle([
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
            story.append(answer_table)
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
        doc.build(story)
        
        # Get PDF content
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create HTTP response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="test_report_{test_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response
        
    except Test.DoesNotExist:
        return JsonResponse({'error': 'Test not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error generating PDF: {str(e)}'}, status=500)