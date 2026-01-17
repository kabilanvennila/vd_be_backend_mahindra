from rest_framework import serializers
from organisation.serializers import SpecValueSerializer,OrganisationSerializer
from testing.models import Feedback, FeedbackAnswer, FeedbackQuestion, Report, Session, Test, TestGPSCoordinate, TestParticipant, TestSpecValue


class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = '__all__'

class TestSpecValueSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)
    spec = SpecValueSerializer(read_only=True)
    
    class Meta:
        model = TestSpecValue
        fields = '__all__'

class TestParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestParticipant
        fields = '__all__'

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

class FeedbackAnswerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating FeedbackAnswer - accepts IDs instead of nested objects"""
    class Meta:
        model = FeedbackAnswer
        fields = ['test', 'question', 'rating', 'comment']

class ReportSerializer(serializers.ModelSerializer):
    test = TestSerializer(read_only=True)

    class Meta:
        model = Report
        fields = '__all__'

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = '__all__'

class FeedbackSerializer(serializers.ModelSerializer):
    audio_file_url = serializers.SerializerMethodField()
    session = SessionSerializer(read_only=True)
    
    class Meta:
        model = Feedback
        fields = ['id', 'session', 'audio_file', 'audio_file_url', 'transcription_text', 
                  'latitude', 'longitude', 'timestamp']
    
    def get_audio_file_url(self, obj):
        """Get full URL for the audio file"""
        if obj.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url
        return None
