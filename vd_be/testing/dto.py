from pydantic import BaseModel, field_validator
from typing import List

class TestParticipantDTO(BaseModel):
    user: int
    role: str

    @field_validator('role')
    def validate_role(cls, value):
        if value not in ['driver', 'passenger']:
            raise ValueError('Role must be either driver or passenger')
        return value

class TestSpecValueDTO(BaseModel):
    spec: int
    isTestingParam: bool

class TestDTO(BaseModel):
    participants: List[TestParticipantDTO]
    spec_values: List[TestSpecValueDTO]

class TestSpecUpdateDTO(BaseModel):
    old_spec_id: int
    new_spec_id: int
    isTestingParam: bool;