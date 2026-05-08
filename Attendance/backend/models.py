from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    roll_number: Optional[str] = None
    role: str = "student" # student, admin, superadmin

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class LeaveRequest(BaseModel):
    date_start: str
    date_end: str
    reason: str

class RemarkCreate(BaseModel):
    roll_number: str
    remark: str

class EnrollmentRequest(BaseModel):
    course_code: str
    section: str
    roll_numbers: list[str]

class TimetableCreate(BaseModel):
    course_code: str
    course_name: Optional[str] = None
    section: str
    faculty_id: Optional[str] = None
    classroom: str
    day: str # e.g. "Monday"
    start_time: str # "10:00"
    end_time: str # "11:00"
    notes: Optional[str] = None
