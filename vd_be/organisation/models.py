from django.db import models
from django.contrib.auth.models import AbstractUser

class Organisation(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    logo_url = models.URLField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, name, description=None, logo_url=None):
        return cls.objects.create(name=name, description=description, logo_url=logo_url)

    @classmethod
    def get_by_id(cls, org_id):
        return cls.objects.get(id=org_id)

    @classmethod
    def update(cls, org_id, **kwargs):
        cls.objects.filter(id=org_id).update(**kwargs)

    @classmethod
    def delete(cls, org_id):
        cls.objects.filter(id=org_id).delete()

    def __str__(self):
        return f"Organisation -- {self.name}"

class User(AbstractUser):
    full_name = models.CharField(max_length=255, blank=True, null=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True, unique=True)
    address = models.TextField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)
    weight = models.FloatField(blank=True, null=True)
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    gender = models.CharField(max_length=255, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture_url = models.URLField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, organisation):
        return cls.objects.create(organisation=organisation)

    @classmethod
    def get_by_id(cls, user_id):
        return cls.objects.get(id=user_id)

    @classmethod
    def update(cls, user_id, **kwargs):
        cls.objects.filter(id=user_id).update(**kwargs)

    @classmethod
    def delete(cls, user_id):
        cls.objects.filter(id=user_id).delete()

class Vehicle(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    body_number = models.CharField(max_length=255, unique=True)
    manufacturer = models.CharField(max_length=255)
    year = models.IntegerField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, organisation, name, manufacturer):
        return cls.objects.create(organisation=organisation, name=name, manufacturer=manufacturer)

    @classmethod
    def get_by_id(cls, vehicle_id):
        return cls.objects.get(id=vehicle_id)

    @classmethod
    def update(cls, vehicle_id, **kwargs):
        cls.objects.filter(id=vehicle_id).update(**kwargs)

    @classmethod
    def delete(cls, vehicle_id):
        cls.objects.filter(id=vehicle_id).delete()

    def __str__(self):
        return f"Vehicle -- {self.name}"

class Project(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=255, unique=True)
    parent_code = models.CharField(max_length=255)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    stage = models.IntegerField(default=0)
    PROJECT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_progress', 'On Progress'),
        ('completed', 'Completed'),
    ]
    status = models.CharField(max_length=50, choices=PROJECT_STATUS_CHOICES, default='active')
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, organisation, name, status):
        return cls.objects.create(organisation=organisation, name=name, status=status)

    @classmethod
    def get_by_id(cls, project_id):
        return cls.objects.get(id=project_id)

    @classmethod
    def update(cls, project_id, **kwargs):
        cls.objects.filter(id=project_id).update(**kwargs)

    @classmethod
    def delete(cls, project_id):
        cls.objects.filter(id=project_id).delete()
    
    def __str__(self):
        return f"Project -- {self.name}"

class ProjectEmployee(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ROLE_CHOICES = [
        ('tester', 'Tester'),
        ('manager', 'Manager'),
    ]
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='tester')
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, project, user, role):
        return cls.objects.create(project=project, user=user, role=role)

    @classmethod
    def get_by_id(cls, pe_id):
        return cls.objects.get(id=pe_id)

    @classmethod
    def update(cls, pe_id, **kwargs):
        cls.objects.filter(id=pe_id).update(**kwargs)

    @classmethod
    def delete(cls, pe_id):
        cls.objects.filter(id=pe_id).delete()

class Spec(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    SPEC_CATEGORY_CHOICES = [
        ('tyre', 'Tyre'),
        ('suspension', 'Suspension'),
        ('brakes', 'Brakes'),
        ('steering', 'Steering'),
        ('engine', 'Engine'),
        ('other', 'Other'),
    ]
    category = models.CharField(max_length=100, choices=SPEC_CATEGORY_CHOICES, default='other')
    title = models.CharField(max_length=255)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, organisation, category, title):
        return cls.objects.create(organisation=organisation, category=category, title=title)

    @classmethod
    def get_by_id(cls, spec_id):
        return cls.objects.get(id=spec_id)

    @classmethod
    def update(cls, spec_id, **kwargs):
        cls.objects.filter(id=spec_id).update(**kwargs)

    @classmethod
    def delete(cls, spec_id):
        cls.objects.filter(id=spec_id).delete()
    
    def __str__(self):
        return f"Spec -- {self.title}"

class SpecValue(models.Model):
    spec = models.ForeignKey(Spec, on_delete=models.CASCADE)
    value = models.CharField(max_length=255, null=True, blank=True)
    VALUE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('boolean', 'Boolean')
    ]
    value_type = models.CharField(max_length=100, choices=VALUE_TYPE_CHOICES, default='text')
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, spec, value):
        return cls.objects.create(spec=spec, value=value)

    @classmethod
    def get_by_id(cls, sv_id):
        return cls.objects.get(id=sv_id)

    @classmethod
    def update(cls, sv_id, **kwargs):
        cls.objects.filter(id=sv_id).update(**kwargs)

    @classmethod
    def delete(cls, sv_id):
        cls.objects.filter(id=sv_id).delete()
    
    def __str__(self):
        return f"Spec Value -- {self.value}"

class VehicleSpec(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    spec = models.ForeignKey(SpecValue, on_delete=models.CASCADE)
    default = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, vehicle, spec, possible_value):
        return cls.objects.create(vehicle=vehicle, spec=spec, possible_value=possible_value)

    @classmethod
    def get_by_id(cls, vs_id):
        return cls.objects.get(id=vs_id)

    @classmethod
    def update(cls, vs_id, **kwargs):
        cls.objects.filter(id=vs_id).update(**kwargs)

    @classmethod
    def delete(cls, vs_id):
        cls.objects.filter(id=vs_id).delete()

class FeedbackQuestion(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    CATEGORY_CHOICES = [
        ('tyre', 'Tyre'),
        ('suspension', 'Suspension'),
        ('brakes', 'Brakes'),
        ('steering', 'Steering'),
        ('engine', 'Engine'),
        ('other', 'Other'),
    ]
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='other')
    question = models.TextField()
    weightage = models.IntegerField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, form, question, weightage):
        return cls.objects.create(form=form, question=question, weightage=weightage)

    @classmethod
    def get_by_id(cls, fq_id):
        return cls.objects.get(id=fq_id)

    @classmethod
    def update(cls, fq_id, **kwargs):
        cls.objects.filter(id=fq_id).update(**kwargs)

    @classmethod
    def delete(cls, fq_id):
        cls.objects.filter(id=fq_id).delete()