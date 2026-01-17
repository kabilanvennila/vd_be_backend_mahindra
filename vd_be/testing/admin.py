from django.contrib import admin
from .models import (
 Feedback, Session, Test, TestParticipant, TestGPSCoordinate, FeedbackAnswer, CategoryScore, Report, TestSpecValue, TestingBenchmarkParams, FeedbackQuestion
)

admin.site.register(Test)
admin.site.register(TestParticipant)
admin.site.register(TestGPSCoordinate)
admin.site.register(FeedbackAnswer)
admin.site.register(CategoryScore)
admin.site.register(Report)
admin.site.register(TestSpecValue)
admin.site.register(Feedback)
admin.site.register(Session)
admin.site.register(TestingBenchmarkParams)
admin.site.register(FeedbackQuestion)
