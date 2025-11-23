from organisation.models import FeedbackQuestion
from rest_framework import serializers
from organisation.serializers import SpecValueSerializer,OrganisationSerializer
from testing.models import Feedback, FeedbackAnswer, Report, Session, Test, TestGPSCoordinate, TestParticipant, TestSpecValue


class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = ['id','project', 'status', 'isReviewed', 'createdAt', 'updatedAt']

class TestSpecValueSerializer(serializers.ModelSerializer):
    spec = SpecValueSerializer()
    class Meta:
        model = TestSpecValue
        fields = ['test', 'spec', 'isTestingParam']

class TestParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestParticipant
        fields = ['test','user', 'role']

class TestGPSCoordinateSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)

    class Meta:
        model = TestGPSCoordinate
        fields = '__all__'

class FeedbackQuestionSerializer(serializers.ModelSerializer):
    organisation = OrganisationSerializer(read_only=True)

    class Meta:
        model = FeedbackQuestion
        fields = '__all__'

class FeedbackAnswerSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)
    question = FeedbackQuestionSerializer(read_only=True)

    class Meta:
        model = FeedbackAnswer
        fields = '__all__'

class ReportSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)

    class Meta:
        model = Report
        fields = '__all__'

class TestSpecValueSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)
    spec_value = SpecValueSerializer(read_only=True)

    class Meta:
        model = TestSpecValue
        fields = '__all__'

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ['id', 'test', 'driver_id', 'vehicle_id', 'start_time']

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'session', 'audio_file', 'latitude', 'longitude', 'timestamp', 'transcription_text']
