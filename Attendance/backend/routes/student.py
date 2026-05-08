from fastapi import APIRouter, Depends, HTTPException
from ..database import attendance_collection, leaves_collection, remarks_collection, students_collection, enrollments_collection, timetables_collection
from ..auth_utils import require_role
from ..models import LeaveRequest
from datetime import datetime
router = APIRouter(prefix="/student", tags=["Student Features"])

# Protect all routes here so only students can access them
# (Though admin/superadmin might want to view this too, we strictly limit to student for now)
def get_student_user(current_user: dict = Depends(require_role(["student"]))):
    if not current_user.get("roll_number"):
        raise HTTPException(status_code=400, detail="Student roll number missing on your profile")
    
    student_db = students_collection.find_one({"roll": current_user["roll_number"]})
    if not student_db:
        raise HTTPException(status_code=404, detail="No face data linked to this account yet. Please register your face at the terminal.")
    
    current_user["real_name"] = student_db.get("name")
    current_user["course"] = student_db.get("course", "N/A")
    current_user["student_class"] = student_db.get("class", "N/A")
    return current_user

@router.get("/attendance")
def get_my_attendance(user: dict = Depends(get_student_user)):
    logs = list(attendance_collection.find({"student_name": user["real_name"]}, {"_id": 0}))
    total_days = len(logs)
    TOTAL_CLASSES = 30
    percentage = round((total_days / TOTAL_CLASSES) * 100, 1)
    
    return {
        "roll_number": user["roll_number"],
        "name": user["real_name"],
        "course": user.get("course", "N/A"),
        "student_class": user.get("student_class", "N/A"),
        "total_days_present": total_days,
        "percentage": percentage,
        "logs": logs
    }

@router.get("/courses")
def get_my_courses(user: dict = Depends(get_student_user)):
    roll = user["roll_number"]
    enrolled_courses = []
    for e in enrollments_collection.find({"roll_numbers": roll}):
        enrolled_courses.append({
            "course_code": e.get("course_code"),
            "section": e.get("section")
        })
    return enrolled_courses

@router.get("/timetables")
def get_my_timetables(user: dict = Depends(get_student_user)):
    """Fetch timetables directly based on student's profile course and class."""
    course = user.get("course")
    section = user.get("student_class")
    
    if not course or not section:
        return []
        
    # Find all timetables for this student's specific batch
    timetables = list(timetables_collection.find(
        {"course_code": course, "section": section}, 
        {"_id": 0}
    ))
    return timetables

@router.get("/remarks")
def get_my_remarks(user: dict = Depends(get_student_user)):
    remarks = list(remarks_collection.find({"roll_number": user["roll_number"]}, {"_id": 0}))
    return remarks

@router.post("/leaves")
def apply_leave(leave: LeaveRequest, user: dict = Depends(get_student_user)):
    leave_data = leave.model_dump()
    leave_data["roll_number"] = user["roll_number"]
    leave_data["student_name"] = user["real_name"]
    leave_data["status"] = "pending"
    leave_data["applied_on"] = datetime.now().isoformat()
    
    leaves_collection.insert_one(leave_data)
    return {"message": "Leave application submitted successfully"}

@router.get("/leaves")
def track_leaves(user: dict = Depends(get_student_user)):
    leaves = list(leaves_collection.find({"roll_number": user["roll_number"]}, {"_id": 0}))
    return leaves
