# Vehicle Development Backend

## Overview
This is the backend repo for Vehicle Development project

## Prerequisites
- Python 3.x
- pip (Python package installer)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the requirements:**
   ```bash
   pip install -r requirements.txt
   ```

## Database Migrations

1. **Apply migrations:**
   Navigate to the `vd_be` directory where `manage.py` is located and run:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
2. **Mock data:**
   To add mock data in DB for testing run:
   ```bash
   python manage.py upsert_mock_data
   ```
## Running the Application

1. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

2. **Access the application:**
   Open your web browser and go to `http://127.0.0.1:8000/`.

## Additional Information
- Add any additional setup or configuration information here.
- Mention any environment variables or settings that need to be configured.

## Contributing
Provide guidelines for contributing to the project.

## License
Include licensing information here.