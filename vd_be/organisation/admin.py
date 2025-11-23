from django.contrib import admin
from .models import (
    Organisation, User, Project, ProjectEmployee, Vehicle, Spec, SpecValue, VehicleSpec, FeedbackQuestion
)

admin.site.register(Organisation)
admin.site.register(User)
admin.site.register(Project)
admin.site.register(ProjectEmployee)
admin.site.register(Vehicle)
admin.site.register(Spec)
admin.site.register(SpecValue)
admin.site.register(VehicleSpec)
admin.site.register(FeedbackQuestion)
