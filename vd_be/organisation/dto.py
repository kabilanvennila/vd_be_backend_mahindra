from pydantic import BaseModel, EmailStr, HttpUrl, field_validator
from typing import Literal
import re
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone_number: str
    address: str = ''
    height: float
    weight: float
    gender: Literal['male', 'female', 'other']
    date_of_birth: str
    profile_picture_url: HttpUrl = None

    @field_validator('password')
    def password_complexity(cls, value):
        if not re.match(r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,}$', value):
            raise ValueError('Password must be at least 8 characters long, include at least one special character(@$!%*?&#), one uppercase letter, and one number.')
        return value

    @field_validator('date_of_birth')
    def validate_date_format(cls, value):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date of birth must be in YYYY-MM-DD format.')
        return value

    @field_validator('phone_number')
    def validate_phone_number(cls, value):
        if not re.match(r'^\d{10}$', value):
            raise ValueError('Phone number must be a valid 10-digit Indian number.')
        return value