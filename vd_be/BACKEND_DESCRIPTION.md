# Vehicle Development Backend (vd_be) - Comprehensive System Description

## Application Overview

**Domain**: Vehicle Testing & Development Management System  
**Purpose**: A Django REST API backend for managing vehicle development projects, test cases, user feedback collection, and test report generation. The system is designed for organizations (specifically Mahindra Vehicle Development) to manage vehicle testing workflows, collect audio feedback during test sessions, and generate comprehensive test reports.

**Technology Stack**:
- **Framework**: Django 5.2
- **API**: Django REST Framework
- **Database**: SQLite3 (development)
- **Authentication**: JWT (JSON Web Tokens) via cookies
- **AI/ML**: OpenAI Whisper for audio transcription
- **PDF Generation**: ReportLab
- **Validation**: Pydantic
- **Language**: Python

---

## Architecture & Project Structure

The backend is organized into Django apps:

1. **`organisation/`** - Core organizational entities (Organizations, Users, Projects, Vehicles, Specs)
2. **`testing/`** - Test management, sessions, feedback, and reporting
3. **`vd_be/`** - Main Django project configuration (settings, URLs, middleware, WSGI)

**Key Files**:
- `settings.py` - Django configuration, database, installed apps, custom user model
- `urls.py` - Root URL routing to all endpoints
- `middleware.py` - JWT authentication decorator
- `manage.py` - Django management script

---

## Database Schema (Models)

### Organisation App Models

#### **Organisation**
- `id` (PrimaryKey)
- `name` (CharField, max_length=255)
- `description` (TextField, nullable)
- `logo_url` (URLField, nullable)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Has many Users, Projects, Vehicles, Specs, FeedbackQuestions

---

#### **User** (Custom User Model, extends AbstractUser)
- `id` (PrimaryKey)
- `username`, `email`, `password` (from AbstractUser)
- `full_name` (CharField, nullable)
- `organisation` (ForeignKey → Organisation, nullable)
- `phone_number` (CharField, unique, nullable) - 10-digit format
- `address` (TextField, nullable)
- `height` (FloatField, nullable)
- `weight` (FloatField, nullable)
- `gender` (CharField, choices: 'male', 'female', 'other', nullable)
- `date_of_birth` (DateField, nullable)
- `profile_picture_url` (URLField, nullable)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation, participates in Tests via TestParticipant, works on Projects via ProjectEmployee

---

#### **Vehicle**
- `id` (PrimaryKey)
- `organisation` (ForeignKey → Organisation)
- `name` (CharField)
- `description` (TextField, nullable)
- `image_url` (URLField, nullable)
- `body_number` (CharField, unique) - Unique vehicle identifier
- `manufacturer` (CharField)
- `year` (IntegerField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation, linked to Projects, has VehicleSpecs

---

#### **Project**
- `id` (PrimaryKey)
- `organisation` (ForeignKey → Organisation)
- `name` (CharField)
- `code` (CharField, unique) - Unique project code
- `parent_code` (CharField)
- `vehicle` (ForeignKey → Vehicle)
- `stage` (IntegerField, default=0)
- `status` (CharField, choices: 'active', 'inactive', 'on_progress', 'completed')
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation and Vehicle, has ProjectEmployees, has Tests

---

#### **ProjectEmployee**
- `id` (PrimaryKey)
- `project` (ForeignKey → Project)
- `user` (ForeignKey → User)
- `role` (CharField, choices: 'tester', 'manager')
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Links Users to Projects with roles

---

#### **Spec**
- `id` (PrimaryKey)
- `organisation` (ForeignKey → Organisation)
- `category` (CharField, choices: 'tyre', 'suspension', 'brakes', 'steering', 'engine', 'other')
- `title` (CharField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation, has SpecValues

---

#### **SpecValue**
- `id` (PrimaryKey)
- `spec` (ForeignKey → Spec)
- `value` (CharField, nullable) - The actual value
- `value_type` (CharField, choices: 'text', 'number', 'boolean')
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Spec, used in VehicleSpecs and TestSpecValues

---

#### **VehicleSpec**
- `id` (PrimaryKey)
- `vehicle` (ForeignKey → Vehicle)
- `spec` (ForeignKey → SpecValue) - Note: references SpecValue, not Spec
- `default` (BooleanField) - Whether this is the default value
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Links Vehicles to SpecValues, forming vehicle specifications

---

### Testing App Models

#### **FeedbackQuestion** (Testing App)
- `id` (PrimaryKey)
- `organisation` (ForeignKey → Organisation)
- `project` (ForeignKey → Project)
- `question` (TextField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation and Project, used in FeedbackAnswers and TestingBenchmarkParams

---

#### **TestingBenchmarkParams**
- `id` (PrimaryKey)
- `organisation` (ForeignKey → Organisation)
- `category` (CharField, choices: 'ride', 'handling', 'Noise', 'Steering')
- `question` (ForeignKey → FeedbackQuestion)
- `weightage` (IntegerField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Organisation, references FeedbackQuestion

**Purpose**: Defines benchmark parameters with categories and weightages for feedback questions

---

#### **Test**
- `id` (PrimaryKey)
- `project` (ForeignKey → Project)
- `status` (CharField, choices: 'pending', 'in_progress', 'completed', 'failed')
- `isReviewed` (BooleanField, default=False)
- `notes` (TextField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Project, has TestParticipants, TestSpecValues, TestGPSCoordinates, Sessions, Reports, FeedbackAnswers

---

#### **TestParticipant**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test)
- `user` (ForeignKey → User)
- `role` (CharField, choices: 'driver', 'passenger')
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Links Users to Tests with test roles (driver/passenger)

---

#### **TestSpecValue**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test)
- `spec` (ForeignKey → SpecValue)
- `isTestingParam` (BooleanField) - Whether this spec is a testing parameter
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Links Tests to SpecValues, tracks which specs are being tested

---

#### **TestGPSCoordinate**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test)
- `lat` (FloatField) - Latitude
- `lon` (FloatField) - Longitude
- `timestamp` (DateTimeField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Test, tracks GPS coordinates during testing

---

#### **Session**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test, nullable) - Optional link to a test
- `driver_id` (CharField, max_length=255) - ID of driver
- `vehicle_id` (CharField, max_length=255) - ID of vehicle
- `start_time` (DateTimeField, auto_now_add)

**Relationships**: Optionally belongs to Test, has Feedbacks

**Purpose**: Represents a testing session where feedback is collected

---

#### **Feedback**
- `id` (PrimaryKey)
- `session` (ForeignKey → Session)
- `audio_file` (FileField) - Uploaded to 'feedback_audios/'
- `latitude` (FloatField, nullable)
- `longitude` (FloatField, nullable)
- `timestamp` (DateTimeField, auto_now_add)
- `transcription_text` (TextField) - Generated by Whisper AI

**Relationships**: Belongs to Session

**Purpose**: Stores audio feedback with GPS location and AI-generated transcription

---

#### **FeedbackAnswer**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test)
- `question` (ForeignKey → FeedbackQuestion)
- `rating` (IntegerField) - Non-negative integer rating
- `comment` (TextField, default='') - Optional text comment
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Links Tests to FeedbackQuestions with structured answers (rating + comment)

**Purpose**: Stores structured feedback answers for test questions. Each answer is associated with a specific test and question. If an answer already exists for a test-question pair, it will be updated rather than creating a duplicate.

---

#### **Report**
- `id` (PrimaryKey)
- `test` (ForeignKey → Test)
- `final_rating` (IntegerField)
- `createdAt`, `updatedAt` (DateTimeField, auto)

**Relationships**: Belongs to Test, final summary of test results

---

## API Endpoints

All endpoints are defined in `vd_be/urls.py`. Most endpoints require JWT authentication via the `@jwt_authentication` decorator (reads JWT from 'jwt' cookie).

### Authentication Endpoints

#### **POST `/login/`**
- **Authentication**: None (public)
- **Request Body**: `LoginRequest` (username, password)
- **Response**: `{ "token": "jwt_token" }` (also sets 'jwt' cookie)
- **Status Codes**: 200 (success), 400 (invalid credentials/validation error), 500 (server error)
- **Purpose**: User authentication, returns JWT token

#### **POST `/signup/`**
- **Authentication**: None (public)
- **Request Body**: `SignupRequest` (username, email, password, phone_number, address, height, weight, gender, date_of_birth, profile_picture_url)
- **Validation**: 
  - Password: min 8 chars, 1 uppercase, 1 digit, 1 special character (@$!%*?&#)
  - Phone: 10-digit number
  - Date: YYYY-MM-DD format
- **Response**: `{ "message": "User created successfully" }`
- **Status Codes**: 201 (created), 400 (validation error), 500 (server error)
- **Purpose**: User registration

---

### User Endpoints

#### **GET `/user/`**
- **Authentication**: Required (JWT)
- **Response**: `{ "user": UserSerializer data }`
- **Status Codes**: 200 (success), 404 (user not found), 500 (error)
- **Purpose**: Get authenticated user's details

#### **GET `/user/projects/`**
- **Authentication**: Required (JWT)
- **Response**: `{ "projects": [ProjectSerializer data] }` - Projects where user is a ProjectEmployee
- **Status Codes**: 200 (success), 404 (user not found), 500 (error)
- **Purpose**: Get all projects associated with the authenticated user

---

### Vehicle Endpoints

#### **GET `/vehicle/<vehicle_id>/specs/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `vehicle_id` (integer)
- **Response**: `{ "vehicle_specs": [VehicleSpecSerializer data] }`
- **Status Codes**: 200 (success), 500 (error)
- **Purpose**: Get all specifications for a vehicle

---

### Project Endpoints

#### **GET `/project/<project_id>/employees/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `project_id` (integer)
- **Response**: `{ "project_employees": [ProjectEmployeeSerializer data] }`
- **Status Codes**: 200 (success), 500 (error)
- **Purpose**: Get all employees (users) associated with a project

---

### Test Endpoints

#### **GET `/project/<project_id>/tests/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `project_id` (integer)
- **Response**: `{ "tests": [Test data with nested spec_values and participants] }`
- **Status Codes**: 200 (success)
- **Purpose**: Get all tests for a project, includes nested TestSpecValues and TestParticipants

#### **POST `/project/<project_id>/test/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `project_id` (integer)
- **Request Body**: `TestDTO`:
  ```json
  {
    "participants": [
      {
        "user": <user_id>,
        "role": "driver" | "passenger"
      }
    ],
    "spec_values": [
      {
        "spec": <spec_value_id>,
        "isTestingParam": boolean
      }
    ]
  }
  ```
- **Validation**: 
  - All participants must be ProjectEmployees of the project
  - Role must be 'driver' or 'passenger'
- **Response**: `{ "message": "success", "id": <test_id> }`
- **Status Codes**: 201 (created), 400 (validation error), 403 (user not in project), 500 (error)
- **Purpose**: Create a new test for a project with participants and spec values

#### **POST `/test/<test_id>/reviewed/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `test_id` (integer)
- **Response**: `{ "message": "success" }`
- **Status Codes**: 200 (success)
- **Purpose**: Mark a test as reviewed (sets `isReviewed = True`)

#### **POST `/test/<test_id>/spec/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `test_id` (integer)
- **Request Body**: `TestSpecUpdateDTO`:
  ```json
  {
    "old_spec_id": <spec_value_id>,
    "new_spec_id": <spec_value_id>,
    "isTestingParam": boolean
  }
  ```
- **Response**: `{ "message": "success" }`
- **Status Codes**: 200 (success)
- **Purpose**: Update a test's spec value (change which spec is being tested)

#### **GET `/test/<test_id>/report/pdf/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `test_id` (integer)
- **Response**: PDF file (application/pdf) with comprehensive test report
- **Status Codes**: 200 (success), 404 (test not found), 500 (error)
- **Purpose**: Generate and download a PDF report for a test
- **Report Contents**:
  - Test information (ID, project, status, dates)
  - Organisation information
  - Vehicle information and specifications
  - Test participants
  - Test specifications
  - GPS coordinates
  - Audio feedback with transcriptions
  - Structured feedback answers
  - Final report rating

---

### Feedback Question & Answer Endpoints

#### **GET `/project/<project_id>/feedback-questions/`**
- **Authentication**: Required (JWT)
- **Path Parameters**: `project_id` (integer)
- **Response**: `{ "questions": [FeedbackQuestionSerializer data] }`
- **Status Codes**: 200 (success), 404 (project not found), 500 (error)
- **Purpose**: Get all feedback questions for a specific project
- **Ordering**: Questions are returned ordered by creation date (newest first)

#### **POST `/feedback-answer/`**
- **Authentication**: Required (JWT)
- **Request Body** (JSON):
  ```json
  {
    "test": <test_id>,
    "question": <question_id>,
    "rating": <integer>,
    "comment": "<optional string>"
  }
  ```
- **Validation**:
  - `test`, `question`, and `rating` are required
  - `test_id` must exist as Test
  - `question_id` must exist as FeedbackQuestion
  - `rating` must be a non-negative integer
  - `comment` is optional (defaults to empty string)
- **Response**: `FeedbackAnswerSerializer data`
- **Status Codes**: 201 (created), 200 (updated), 400 (validation error), 404 (test/question not found), 500 (error)
- **Purpose**: Create or update a feedback answer for a test
- **Behavior**: If an answer already exists for the same test-question pair, it will be updated instead of creating a duplicate

---

### Session & Feedback Endpoints

#### **POST `/start-session/`**
- **Authentication**: Required (JWT)
- **Request Body** (form-data or JSON):
  ```json
  {
    "driver_id": <user_id>,
    "vehicle_id": <vehicle_id>,
    "test_id": <test_id>  // optional
  }
  ```
- **Validation**:
  - driver_id and vehicle_id are required
  - driver_id must exist as User
  - vehicle_id must exist as Vehicle
  - test_id (if provided) must exist as Test
- **Response**: `SessionSerializer data`
- **Status Codes**: 201 (created), 400 (validation error), 500 (error)
- **Purpose**: Start a new testing session, optionally linked to a test

#### **POST `/upload-feedback/`**
- **Authentication**: Required (JWT)
- **Request Body** (multipart/form-data):
  - `session_id` (required) - ID of the session
  - `file` (required) - Audio file (mpeg, mp3, wav, m4a, x-m4a, aac)
  - `latitude` (optional) - Float between -90 and 90
  - `longitude` (optional) - Float between -180 and 180
- **Validation**:
  - Audio file max size: 10MB
  - Valid audio MIME types
  - Valid GPS coordinates if provided
- **Response**: `FeedbackSerializer data` (includes transcription_text if successful)
- **Status Codes**: 201 (created), 400 (validation error), 404 (session not found), 500 (error)
- **Purpose**: Upload audio feedback for a session
- **AI Processing**: Automatically transcribes audio using OpenAI Whisper model ("base")
- **Note**: Transcription failures don't fail the request; feedback is created with transcription_error in response if transcription fails

---

## Authentication & Authorization

### JWT Authentication

- **Method**: JWT tokens stored in HTTP-only cookies
- **Cookie Name**: `jwt`
- **Algorithm**: HS256
- **Secret Key**: From Django settings (`SECRET_KEY`)
- **Token Payload**:
  ```json
  {
    "user_id": <user_id>,
    "exp": <expiration_timestamp>,
    "iat": <issued_at_timestamp>
  }
  ```
- **Token Expiration**: 24 hours from issuance
- **Implementation**: Custom `@jwt_authentication` decorator in `vd_be/middleware.py`
- **Behavior**: 
  - Reads token from 'jwt' cookie
  - Validates token and extracts user_id
  - Sets `request.user_id` for use in views
  - Returns 401 if token is missing, invalid, or expired

### Authorization

- Most endpoints require JWT authentication
- Project-specific endpoints may validate user membership via ProjectEmployee
- Test creation validates that all participants are ProjectEmployees of the project

---

## Key Features & Workflows

### 1. User Management
- Custom User model with extended profile fields (height, weight, gender, DOB, etc.)
- User registration with password complexity validation
- JWT-based authentication with cookie storage

### 2. Organization Structure
- Multi-tenant architecture: Organizations → Projects → Tests
- Vehicles belong to organizations
- Users belong to organizations
- Projects link organizations, vehicles, and users

### 3. Vehicle Specifications
- Hierarchical spec system: Spec (category, title) → SpecValue (value, value_type)
- VehicleSpec links vehicles to SpecValues
- Specs organized by categories: tyre, suspension, brakes, steering, engine, other

### 4. Test Management
- Tests belong to Projects
- Tests track status: pending, in_progress, completed, failed
- Tests can be reviewed (isReviewed flag)
- Tests link to SpecValues via TestSpecValue (with isTestingParam flag)
- Tests have participants (TestParticipant) with roles: driver, passenger
- Tests can have GPS coordinates (TestGPSCoordinate)

### 5. Feedback Collection
- **Session-based**: Sessions represent active testing periods
- **Audio Feedback**: Upload audio files during sessions with GPS coordinates
- **AI Transcription**: Automatic transcription using OpenAI Whisper
- **Structured Feedback Questions**: Questions are associated with projects and organizations
- **Structured Feedback Answers**: FeedbackAnswers link tests to FeedbackQuestions with ratings and comments
  - Questions are fetched per project via `/project/<id>/feedback-questions/`
  - Answers are posted via `/feedback-answer/` with test_id, question_id, rating, and optional comment
  - Answers are automatically updated if they already exist for a test-question pair
- **Benchmark Parameters**: TestingBenchmarkParams define categories and weightages for questions

### 6. Report Generation
- Comprehensive PDF reports generated via ReportLab
- Includes all test-related data:
  - Test details, organization, vehicle info
  - Vehicle specifications
  - Test participants
  - Test specifications
  - GPS coordinates
  - Audio feedback with transcriptions
  - Structured feedback answers
  - Final report rating

---

## Data Flow Examples

### Creating a Test
1. User authenticates via `/login/` → receives JWT token
2. User creates test via `POST /project/<id>/test/` with:
   - Participants (users with roles)
   - Spec values to test
3. System validates:
   - All participants are ProjectEmployees of the project
   - Spec values exist
4. System creates:
   - Test record
   - TestParticipant records
   - TestSpecValue records
5. Returns test ID

### Collecting Feedback

#### Audio Feedback Flow
1. Start session: `POST /start-session/` with driver_id, vehicle_id, optional test_id
2. During session, upload feedback: `POST /upload-feedback/` with:
   - session_id
   - audio file
   - GPS coordinates (optional)
3. System:
   - Validates session exists
   - Validates audio file
   - Saves Feedback record
   - Transcribes audio using Whisper AI
   - Updates Feedback with transcription_text
4. Returns feedback data with transcription

#### Structured Feedback Flow
1. Fetch questions: `GET /project/<project_id>/feedback-questions/` to get all questions for a project
2. For each question, submit answer: `POST /feedback-answer/` with:
   - test_id
   - question_id
   - rating (integer)
   - comment (optional string)
3. System:
   - Validates test and question exist
   - Validates rating is a non-negative integer
   - Creates new FeedbackAnswer or updates existing one if answer already exists for test-question pair
4. Returns FeedbackAnswer data

### Generating Report
1. Request PDF: `GET /test/<id>/report/pdf/`
2. System fetches all related data:
   - Test, Project, Organisation, Vehicle
   - Participants, SpecValues, GPS coordinates
   - Sessions, Feedbacks (with transcriptions)
   - FeedbackAnswers, Report
3. System generates PDF using ReportLab with structured layout
4. Returns PDF file as download

---

## Serializers (Data Transfer Objects)

### Organisation App Serializers
- **UserSerializer**: Full user details (excludes sensitive fields)
- **UserLiteSerializer**: Minimal user data (id, full_name)
- **VehicleSerializer**: Vehicle details
- **ProjectSerializer**: Project details with nested Vehicle
- **ProjectEmployeeSerializer**: Project employee with nested User
- **SpecSerializer**: Spec details (category, title)
- **SpecValueSerializer**: SpecValue with nested Spec
- **VehicleSpecSerializer**: VehicleSpec with nested SpecValue
- **OrganisationSerializer**: Full organization data

### Testing App Serializers
- **TestSerializer**: Test details (id, project, status, isReviewed, dates)
- **TestSpecValueSerializer**: TestSpecValue with nested Test and SpecValue
- **TestParticipantSerializer**: TestParticipant details
- **TestGPSCoordinateSerializer**: GPS coordinate data
- **SessionSerializer**: Session details
- **FeedbackSerializer**: Feedback with transcription
- **FeedbackQuestionSerializer**: FeedbackQuestion with nested Organisation
- **FeedbackAnswerSerializer**: FeedbackAnswer with nested Test and FeedbackQuestion (read-only)
- **FeedbackAnswerCreateSerializer**: FeedbackAnswer creation (accepts IDs for test and question)
- **ReportSerializer**: Report with nested Test

---

## DTOs (Request Validation)

### Organisation DTOs (`organisation/dto.py`)
- **LoginRequest**: username, password
- **SignupRequest**: username, email, password, phone_number, address, height, weight, gender, date_of_birth, profile_picture_url
  - Password validation: min 8 chars, 1 uppercase, 1 digit, 1 special char
  - Phone validation: 10 digits
  - Date validation: YYYY-MM-DD format

### Testing DTOs (`testing/dto.py`)
- **TestParticipantDTO**: user (id), role ('driver' | 'passenger')
- **TestSpecValueDTO**: spec (id), isTestingParam (boolean)
- **TestDTO**: participants (list of TestParticipantDTO), spec_values (list of TestSpecValueDTO)
- **TestSpecUpdateDTO**: old_spec_id, new_spec_id, isTestingParam

---

## External Dependencies & Services

### OpenAI Whisper
- **Purpose**: Audio transcription
- **Model**: "base" (loaded at module level in `testing/views.py`)
- **Usage**: Transcribes uploaded audio feedback files
- **Integration**: Called synchronously during feedback upload

### ReportLab
- **Purpose**: PDF generation
- **Usage**: Generates comprehensive test reports
- **Features**: Tables, paragraphs, styling, page breaks

---

## Database Configuration

- **Engine**: SQLite3 (development)
- **Location**: `vd_be/db.sqlite3`
- **Migrations**: Located in `organisation/migrations/` and `testing/migrations/`
- **Custom User Model**: `organisation.User` (set via `AUTH_USER_MODEL` in settings)

---

## Middleware & Security

### JWT Authentication Middleware
- Custom decorator: `@jwt_authentication`
- Location: `vd_be/middleware.py`
- Reads JWT from cookies
- Validates token and extracts user_id
- Returns 401 for authentication failures

### CSRF Protection
- Django CSRF middleware enabled
- CSRF exempt on some endpoints (using `@csrf_exempt`)

---

## File Storage

- **Audio Files**: Stored in `vd_be/feedback_audios/` directory
- **File Upload**: Handled via Django FileField
- **Supported Formats**: mpeg, mp3, wav, m4a, x-m4a, aac
- **Max Size**: 10MB per file

---

## Notes for AI Agents

1. **User Context**: Always check `request.user_id` (set by JWT middleware) to identify the authenticated user
2. **Relationships**: Many models have cascading deletes (CASCADE) - be aware when deleting parent records
3. **Validation**: Use Pydantic DTOs for request validation, Django serializers for response formatting
4. **Error Handling**: Most views return JsonResponse with error messages and appropriate HTTP status codes
5. **Transcription**: Whisper model is loaded globally - transcription happens synchronously and may take time for large files
6. **Reports**: PDF generation is comprehensive and includes all related data - may be slow for tests with many records
7. **Sessions**: Sessions are independent entities that can optionally link to Tests - this allows feedback collection outside of formal test structures

