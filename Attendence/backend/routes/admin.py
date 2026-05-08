from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from ..database import attendance_collection, leaves_collection, remarks_collection, students_collection
from ..auth_utils import require_role
from ..models import RemarkCreate
from datetime import datetime
from bson import ObjectId
import pandas as pd
import io
# PDF generation imports
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

router = APIRouter(prefix="/admin", tags=["Admin Features"])

admin_dep = Depends(require_role(["admin", "superadmin"]))

@router.get("/export/excel")
def export_attendance_excel(user: dict = admin_dep):
    """Export all attendance logs to a professional Excel sheet."""
    logs = list(attendance_collection.find({}, {"_id": 0}))
    if not logs:
        raise HTTPException(status_code=404, detail="No attendance records to export.")
    
    df = pd.DataFrame(logs)
    
    # Reorder columns for professional look
    cols = ["student_name", "roll", "date", "time", "status", "confidence"]
    available_cols = [c for c in cols if c in df.columns]
    df = df[available_cols]
    
    # Rename columns for clarity
    rename_map = {
        "student_name": "Student Name",
        "roll": "Roll Number",
        "date": "Date",
        "time": "Time",
        "status": "Status",
        "confidence": "Recognition Confidence"
    }
    df.rename(columns=rename_map, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance Report')
    
    output.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Attendance_Report_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@router.get("/export/pdf")
def export_attendance_pdf(user: dict = admin_dep):
    """Export all attendance logs to a college-standard PDF report."""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=501, detail="PDF generation library (reportlab) not installed on server.")
        
    logs = list(attendance_collection.find({}, {"_id": 0}).sort("date", -1))
    if not logs:
        raise HTTPException(status_code=404, detail="No attendance records to export.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Smart Attendance System - Attendance Report", styles['Title']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Table Data
    data = [["Name", "Roll", "Date", "Time", "Status", "Conf."]]
    for log in logs:
        data.append([
            log.get("student_name", "N/A"),
            log.get("roll", "N/A"),
            log.get("date", "N/A"),
            log.get("time", "N/A"),
            log.get("status", "Present"),
            f"{log.get('confidence', 0):.2f}" if log.get('confidence') else "N/A"
        ])

    # Table Styling
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Attendance_Report_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    return StreamingResponse(buffer, headers=headers, media_type='application/pdf')

router = APIRouter(prefix="/admin", tags=["Admin Features"])

admin_dep = Depends(require_role(["admin", "superadmin"]))

@router.get("/attendance")
def get_all_attendance(user: dict = admin_dep):
    logs = list(attendance_collection.find({}, {"_id": 0}))
    return logs

@router.get("/students")
def get_all_students(user: dict = admin_dep):
    """Return all registered students with their attendance count, class, and course."""
    students = list(students_collection.find({}, {"embedding": 0, "_id": 0}))
    
    # Get attendance count per student roll number
    pipeline = [
        {"$group": {"_id": "$roll", "present_days": {"$sum": 1}}}
    ]
    attendance_counts = {r["_id"]: r["present_days"] for r in attendance_collection.aggregate(pipeline)}
    
    # Calculate total classes based on unique dates in the system
    # This represents 'sessions held so far'
    unique_dates = attendance_collection.distinct("date")
    TOTAL_CLASSES = len(unique_dates) if len(unique_dates) > 0 else 1
    
    result = []
    for s in students:
        roll_num = s.get("roll")
        present = attendance_counts.get(roll_num, 0)
        percentage = round((present / TOTAL_CLASSES) * 100, 1) if TOTAL_CLASSES > 0 else 0
        result.append({
            "name": s.get("name"),
            "roll": s.get("roll"),
            "class": s.get("class", "N/A"),
            "course": s.get("course", "N/A"),
            "contact": s.get("contact", "N/A"),
            "present_days": present,
            "percentage": percentage,
            "enrolled_at": str(s.get("enrolled_at", ""))
        })
    
    return result

@router.patch("/students/{roll}")
def update_student(roll: str, body: dict, user: dict = admin_dep):
    """Update student's course, class, or contact by roll number."""
    allowed_fields = {"course", "class", "contact", "name"}
    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update.")
    
    result = students_collection.update_one({"roll": roll}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Student with roll '{roll}' not found.")
        
    # Sync with enrollments_collection if course and class are provided/updated
    # It's safest to pull from all and push to the new one if we only have one enrollment
    # per student in the simplified model.
    # Sync with enrollments_collection if course or class is updated
    if "course" in update_data or "class" in update_data:
        # Get latest full data to ensure we have both course and class
        student = students_collection.find_one({"roll": roll})
        course_code = update_data.get("course", student.get("course"))
        section = update_data.get("class", student.get("class"))
        
        # Remove from all previous enrollments for this roll
        from database import enrollments_collection
        enrollments_collection.update_many(
            {"roll_numbers": roll},
            {"$pull": {"roll_numbers": roll}}
        )
        
        # Add to the new enrollment batch
        if course_code and section:
            enrollments_collection.update_one(
                {"course_code": course_code, "section": section},
                {"$addToSet": {"roll_numbers": roll}},
                upsert=True
            )
            
    return {"message": "Student updated successfully."}

@router.delete("/students/{roll}")
def delete_student(roll: str, user: dict = admin_dep):
    """Remove a student from the system by roll number."""
    # Fetch the student BEFORE deleting so we have their name.
    # Attendance records are keyed on student_name (not roll), so we need
    # the name to correctly cascade-delete attendance data.
    student = students_collection.find_one({"roll": roll}, {"name": 1})
    if not student:
        raise HTTPException(status_code=404, detail=f"Student with roll '{roll}' not found.")

    student_name = student.get("name")

    # Delete the student document
    students_collection.delete_one({"roll": roll})

    # Remove their attendance records using the unique roll
    deleted = attendance_collection.delete_many({"roll": roll})
    
    # Cascade delete to enrollments_collection
    from database import enrollments_collection, users_collection
    enrollments_collection.update_many(
        {"roll_numbers": roll},
        {"$pull": {"roll_numbers": roll}}
    )
    
    # Cascade delete to users_collection (Auth account)
    users_collection.delete_one({"roll_number": roll})

    return {
        "message": f"Student '{student_name}' (roll: {roll}) removed successfully.",
        "attendance_records_deleted": deleted.deleted_count,
    }


@router.get("/defaulters")
def get_defaulters(user: dict = admin_dep):
    # This is a simplified aggregator.
    # Count occurrences of a student in attendance, compare to a required threshold.
    # In production, use MongoDB Aggregation pipelines.
    
    pipeline = [
        {"$group": {"_id": "$roll", "present_days": {"$sum": 1}}}
    ]
    attendance_counts = list(attendance_collection.aggregate(pipeline))
    
    # Calculate total classes based on unique dates in the system
    unique_dates = attendance_collection.distinct("date")
    TOTAL_CLASSES = len(unique_dates) if len(unique_dates) > 0 else 1
    
    defaulters = []
    
    for record in attendance_counts:
        roll_num = record["_id"]
        percent = (record["present_days"] / TOTAL_CLASSES) * 100
        if percent < 75.0:
            student = students_collection.find_one({"roll": roll_num}, {"name": 1})
            name = student.get("name") if student else "Unknown"
            defaulters.append({
                "student_name": name,
                "roll": roll_num,
                "present_days": record["present_days"],
                "percentage": round(percent, 2)
            })
            
    return defaulters

@router.post("/remarks")
def add_remark(remark: RemarkCreate, user: dict = admin_dep):
    # Check if student exists
    student = students_collection.find_one({"roll": remark.roll_number})
    if not student:
        raise HTTPException(status_code=404, detail="Student roll number not found")
        
    remark_data = remark.model_dump()
    remark_data["admin_email"] = user["email"]
    remark_data["date"] = datetime.now().isoformat()
    
    remarks_collection.insert_one(remark_data)
    return {"message": "Remark successfully added"}

@router.get("/leaves")
def view_all_leaves(user: dict = admin_dep):
    leaves = list(leaves_collection.find({}, {"_id": 1, "student_name": 1, "roll_number": 1, "date_start": 1, "date_end": 1, "reason": 1, "status": 1}))
    # Convert ObjectIds to string safely
    for leave in leaves:
        leave["_id"] = str(leave["_id"])
    return leaves

@router.patch("/leaves/{leave_id}")
def update_leave_status(leave_id: str, status: str, user: dict = admin_dep):
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")
        
    result = leaves_collection.update_one(
        {"_id": ObjectId(leave_id)}, 
        {"$set": {"status": status}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    return {"message": f"Leave {status} successfully"}
