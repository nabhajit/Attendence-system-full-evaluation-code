from pymongo import MongoClient
import os
import sys
import pathlib

# Load the environment
_attendance_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_attendance_dir))

from dotenv import load_dotenv
load_dotenv(_attendance_dir / ".env", override=True)

# Connect to DB
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME", "smart_attendance")]
students_collection = db["students"]
enrollments_collection = db["enrollments"]

print("Starting migration of students to enrollments...")

students = list(students_collection.find({}))
count = 0

for student in students:
    roll = student.get("roll")
    course = student.get("course")
    section = student.get("class")
    
    if roll and course and section and course != "N/A" and section != "N/A":
        # Add to enrollment
        result = enrollments_collection.update_one(
            {"course_code": course, "section": section},
            {"$addToSet": {"roll_numbers": roll}},
            upsert=True
        )
        if result.modified_count > 0 or result.upserted_id:
            count += 1
            print(f"Migrated student {roll} to {course} - {section}")

print(f"Migration complete. {count} students synced to enrollments.")
