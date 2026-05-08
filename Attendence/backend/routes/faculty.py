from fastapi import APIRouter, HTTPException, Depends
from typing import List
from ..models import EnrollmentRequest, TimetableCreate
from ..database import subjects_collection, enrollments_collection, timetables_collection, students_collection
from ..auth_utils import require_role
router = APIRouter(prefix="/faculty", tags=["Faculty"])
faculty_dep = Depends(require_role(["admin", "superadmin"]))

@router.get("/courses/search")
def search_courses(user: dict = faculty_dep):
    pipeline = [
        {"$group": {
            "_id": {"course_code": "$course_code", "course_name": "$course_name", "section": "$section"}
        }},
        {"$project": {
            "_id": 0,
            "course_code": "$_id.course_code",
            "course_name": "$_id.course_name",
            "section": "$_id.section"
        }}
    ]
    results = list(timetables_collection.aggregate(pipeline))
    return results

@router.post("/enroll")
def enroll_students(req: EnrollmentRequest, user: dict = faculty_dep):
    valid_rolls = []
    for roll in req.roll_numbers:
        if students_collection.find_one({"roll_number": roll}):
            valid_rolls.append(roll)
            
    if not valid_rolls:
        raise HTTPException(status_code=400, detail="No valid students found to enroll")
        
    enrollments_collection.update_one(
        {"course_code": req.course_code, "section": req.section},
        {"$addToSet": {"roll_numbers": {"$each": valid_rolls}}},
        upsert=True
    )
    return {"message": f"Successfully enrolled {len(valid_rolls)} students"}

@router.get("/enrollments/{course_code}/{section}")
def get_enrollments(course_code: str, section: str, user: dict = faculty_dep):
    enrollment = enrollments_collection.find_one({"course_code": course_code, "section": section}, {"_id": 0})
    return enrollment.get("roll_numbers", []) if enrollment else []

@router.post("/timetables")
def schedule_timetable(tt: TimetableCreate, user: dict = faculty_dep):
    data = tt.model_dump()
    data["faculty_id"] = user.get("email", "unknown")
    timetables_collection.insert_one(data)
    return {"message": "Timetable scheduled successfully"}

@router.get("/timetables")
def get_timetables(user: dict = faculty_dep):
    tts = list(timetables_collection.find({}, {"_id": 0}))
    # Convert ObjectId to str if needed, but {"_id": 0} avoids it.
    return tts

@router.delete("/timetables/{course_code}/{section}/{day}/{start_time}")
def delete_timetable(course_code: str, section: str, day: str, start_time: str, user: dict = faculty_dep):
    res = timetables_collection.delete_one({
        "course_code": course_code, 
        "section": section, 
        "day": day, 
        "start_time": start_time
    })
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return {"message": "Timetable deleted"}

@router.put("/timetables/{course_code}/{section}/{day}/{start_time}")
def update_timetable(course_code: str, section: str, day: str, start_time: str, tt: TimetableCreate, user: dict = faculty_dep):
    data = tt.model_dump()
    data["faculty_id"] = user.get("email", "unknown")
    res = timetables_collection.replace_one(
        {
            "course_code": course_code, 
            "section": section, 
            "day": day, 
            "start_time": start_time
        },
        data
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Original timetable not found")
    return {"message": "Timetable updated successfully"}
