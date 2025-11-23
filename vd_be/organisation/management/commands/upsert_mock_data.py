from django.core.management.base import BaseCommand
from django.conf import settings
from organisation.models import Organisation, Project, ProjectEmployee, Vehicle, Spec, SpecValue, VehicleSpec, FeedbackQuestion
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Upsert mock data for testing purposes'

    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            self.stdout.write(self.style.ERROR('This command can only be run in DEBUG mode.'))
            return

        # Upsert Organisations
        org, created = Organisation.objects.update_or_create(
            name='Test Organisation',
            defaults={'description': 'A test organisation', 'logo_url': 'http://example.com/logo.png'}
        )
        self.stdout.write(self.style.SUCCESS(f'Organisation {"created" if created else "updated"}: {org.name}'))

        # Upsert Vehicles
        vehicle, created = Vehicle.objects.update_or_create(
            organisation=org,
            name='Test Vehicle',
            defaults={'description': 'A test vehicle', 'body_number': 'BN001', 'manufacturer': 'Test Manufacturer', 'year': 2023}
        )
        self.stdout.write(self.style.SUCCESS(f'Vehicle {"created" if created else "updated"}: {vehicle.name}'))
        
        # Upsert Projects
        project, created = Project.objects.update_or_create(
            organisation=org,
            name='Test Project',
            vehicle=vehicle,
            defaults={'code': 'TP001', 'parent_code': 'TP000', 'status': 'active'}
        )
        self.stdout.write(self.style.SUCCESS(f'Project {"created" if created else "updated"}: {project.name}'))

        # Upsert Specs
        spec1, created = Spec.objects.update_or_create(
            organisation=org,
            title='Test Spec 1',
            defaults={'category': 'engine'}
        )
        self.stdout.write(self.style.SUCCESS(f'Spec 1 {"created" if created else "updated"}: {spec1.title}'))
        
        spec2, created = Spec.objects.update_or_create(
            organisation=org,
            title='Test Spec 2',
            defaults={'category': 'brakes'}
        )
        self.stdout.write(self.style.SUCCESS(f'Spec 2 {"created" if created else "updated"}: {spec2.title}'))
        
        spec3, created = Spec.objects.update_or_create(
            organisation=org,
            title='Test Spec 3',
            defaults={'category': 'brakes'}
        )
        self.stdout.write(self.style.SUCCESS(f'Spec 3 {"created" if created else "updated"}: {spec3.title}'))
        
        spec4, created = Spec.objects.update_or_create(
            organisation=org,
            title='Test Spec 4',
            defaults={'category': 'suspension'}
        )
        self.stdout.write(self.style.SUCCESS(f'Spec 4 {"created" if created else "updated"}: {spec4.title}'))

        # Upsert SpecValues
        spec_value1, created = SpecValue.objects.update_or_create(
            spec=spec1,
            value='Test Value 1',
            defaults={'value_type': 'text'}
        )
        self.stdout.write(self.style.SUCCESS(f'SpecValue 1 {"created" if created else "updated"}: {spec_value1.value}'))
        
        spec_value2, created = SpecValue.objects.update_or_create(
            spec=spec2,
            value='Test Value 2',
            defaults={'value_type': 'text'}
        )
        self.stdout.write(self.style.SUCCESS(f'SpecValue 2 {"created" if created else "updated"}: {spec_value2.value}'))
        
        spec_value3, created = SpecValue.objects.update_or_create(
            spec=spec3,
            value='Test Value 3',
            defaults={'value_type': 'text'}
        )
        self.stdout.write(self.style.SUCCESS(f'SpecValue 3 {"created" if created else "updated"}: {spec_value3.value}'))
        
        spec_value4, created = SpecValue.objects.update_or_create(
            spec=spec4,
            value='Test Value 4',
            defaults={'value_type': 'text'}
        )
        self.stdout.write(self.style.SUCCESS(f'SpecValue 4 {"created" if created else "updated"}: {spec_value4.value}'))

        # Upsert FeedbackQuestions
        feedback_question, created = FeedbackQuestion.objects.update_or_create(
            organisation=org,
            question='How do you rate the test vehicle?',
            defaults={'category': 'engine', 'weightage': 5}
        )
        self.stdout.write(self.style.SUCCESS(f'FeedbackQuestion {"created" if created else "updated"}: {feedback_question.question}'))

        # Upsert ProjectEmployee
        user = User.objects.first()  # Assuming there's at least one user in the database
        if user:
            project_employee, created = ProjectEmployee.objects.update_or_create(
                project=project,
                user=user,
                defaults={'role': 'manager'}
            )
            self.stdout.write(self.style.SUCCESS(f'ProjectEmployee {"created" if created else "updated"}: {project_employee.role} for user {user.username}'))

        # Upsert VehicleSpec
        VehicleSpec.objects.update_or_create(
            vehicle=vehicle,
            spec=spec_value1
        )
        VehicleSpec.objects.update_or_create(
            vehicle=vehicle,
            spec=spec_value2
        )
        VehicleSpec.objects.update_or_create(
            vehicle=vehicle,
            spec=spec_value3
        )
        VehicleSpec.objects.update_or_create(
            vehicle=vehicle,
            spec=spec_value4
        )
        self.stdout.write(self.style.SUCCESS(f'VehicleSpec created: Vehicle {vehicle.name}'))
