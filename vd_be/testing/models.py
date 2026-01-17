from django.db import models

from organisation.models import Organisation, Project, SpecValue, User, Vehicle

class Test(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    TEST_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('yet_to_test', 'Yet to test'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=50, choices=TEST_STATUS_CHOICES, default='pending')
    isReviewed = models.BooleanField(default=False)
    notes = models.TextField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, project, vehicle, status):
        return cls.objects.create(project=project, vehicle=vehicle, status=status)

    @classmethod
    def get_by_id(cls, test_id):
        return cls.objects.get(id=test_id)

    @classmethod
    def update(cls, test_id, **kwargs):
        cls.objects.filter(id=test_id).update(**kwargs)

    @classmethod
    def delete(cls, test_id):
        cls.objects.filter(id=test_id).delete()

class TestParticipant(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ROLE_CHOICES = [
        ('driver', 'Driver'),
        ('passenger', 'Passenger'),
    ]
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='driver')
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, test, user, role):
        return cls.objects.create(test=test, user=user, role=role)

    @classmethod
    def get_by_id(cls, tp_id):
        return cls.objects.get(id=tp_id)

    @classmethod
    def update(cls, tp_id, **kwargs):
        cls.objects.filter(id=tp_id).update(**kwargs)

    @classmethod
    def delete(cls, tp_id):
        cls.objects.filter(id=tp_id).delete()

class TestSpecValue(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    spec = models.ForeignKey(SpecValue, on_delete=models.CASCADE)
    isTestingParam = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, test, spec_value):
        return cls.objects.create(test=test, spec_value=spec_value)

    @classmethod
    def get_by_id(cls, tsv_id):
        return cls.objects.get(id=tsv_id)

    @classmethod
    def update(cls, tsv_id, **kwargs):
        cls.objects.filter(id=tsv_id).update(**kwargs)

    @classmethod
    def delete(cls, tsv_id):
        cls.objects.filter(id=tsv_id).delete()

class TestGPSCoordinate(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    lat = models.FloatField()
    lon = models.FloatField()
    timestamp = models.DateTimeField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, test, lat, lon, timestamp):
        return cls.objects.create(test=test, lat=lat, lon=lon, timestamp=timestamp)

    @classmethod
    def get_by_id(cls, tgc_id):
        return cls.objects.get(id=tgc_id)

    @classmethod
    def update(cls, tgc_id, **kwargs):
        cls.objects.filter(id=tgc_id).update(**kwargs)

    @classmethod
    def delete(cls, tgc_id):
        cls.objects.filter(id=tgc_id).delete()

class FeedbackQuestion(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    question = models.TextField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Project {self.project} - rating {self.question}"

class TestingBenchmarkParams(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    CATEGORY_CHOICES = [
        ('ride', 'Ride'),
        ('handling', 'Handling'),
        ('Noise', 'noise'),
        ('Steering', 'steering')
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    question = models.ForeignKey(FeedbackQuestion, on_delete=models.CASCADE)
    weightage = models.IntegerField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"category {self.category} - question {self.question}"
        
class FeedbackAnswer(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    question = models.ForeignKey(FeedbackQuestion, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(default='')
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment {self.comment} - rating {self.rating}"

class CategoryScore(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='category_scores')
    category = models.CharField(max_length=100)
    score = models.FloatField()  # Final calculated score for this category
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['test', 'category']  # One score per category per test

    def __str__(self):
        return f"Test {self.test.id} - {self.category}: {self.score}"

class Report(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    final_rating = models.IntegerField()
    pdf_file = models.FileField(upload_to='reports/', null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, test, final_rating):
        return cls.objects.create(test=test, final_rating=final_rating)

    @classmethod
    def get_by_id(cls, report_id):
        return cls.objects.get(id=report_id)

    @classmethod
    def update(cls, report_id, **kwargs):
        cls.objects.filter(id=report_id).update(**kwargs)

    @classmethod
    def delete(cls, report_id):
        cls.objects.filter(id=report_id).delete()


class Session(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, null=True, blank=True, related_name='sessions')
    driver_id = models.CharField(max_length=255)
    vehicle_id = models.CharField(max_length=255)
    start_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.id} - Driver {self.driver_id}"

class Feedback(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='feedbacks')
    audio_file = models.FileField(upload_to='feedback_audios/')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    transcription_text = models.TextField(blank=True)

    def __str__(self):
        return f"Feedback {self.id} for Session {self.session.id}"