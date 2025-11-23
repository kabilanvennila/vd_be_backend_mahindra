"""
URL configuration for vd_be project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from organisation.views import login_view, signup_view, user_details_view, user_projects_view, project_employees_view, vehicle_specs_view
from testing.views import get_project_tests_view, create_test_view, mark_test_as_reviewed, update_test_spec_value_view
from testing.views import upload_feedback, start_session, generate_test_report_pdf

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('user/', user_details_view, name='user_details'),
    path('user/projects/', user_projects_view, name='user_projects'),
    path('vehicle/<int:vehicle_id>/specs/', vehicle_specs_view, name='vehicle_specs'),
    path('project/<int:project_id>/employees/', project_employees_view, name='project_employees'),
    path('project/<int:project_id>/tests/', get_project_tests_view, name='get_project_tests'),
    path('project/<int:project_id>/test/', create_test_view, name='create_test'),
    path('test/<int:test_id>/reviewed/', mark_test_as_reviewed, name='mark_test_as_reviewed'),
    path('test/<int:test_id>/spec/', update_test_spec_value_view, name='update_test_spec_value'),
    path('test/<int:test_id>/report/pdf/', generate_test_report_pdf, name='generate_test_report_pdf'),
    path('start-session/', start_session, name='start_session'),
    path('upload-feedback/', upload_feedback, name='upload_feedback'),
]
