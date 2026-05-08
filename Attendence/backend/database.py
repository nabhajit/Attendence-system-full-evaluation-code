import os
import pymongo
from datetime import datetime
from . import env_loader

MONGO_URI = os.getenv("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["smart_attendance_db"]

# Collections
users_collection = db["users"]
students_collection = db["students"]
attendance_collection = db["attendance"]
leaves_collection = db["leaves"]
remarks_collection = db["remarks"]

# New Collections for Subject-wise Workflow
subjects_collection = db["subjects"]
enrollments_collection = db["enrollments"]
timetables_collection = db["timetables"]
password_resets_collection = db["password_resets"]

def init_db():
    # Ensure indexes for unique constraints
    users_collection.create_index("email", unique=True)
    users_collection.create_index("roll_number")
    
    # Check if a superadmin exists. If not, create a fallback one.
    if users_collection.count_documents({"role": "superadmin"}) == 0:
        from auth_utils import get_password_hash
        print("Initializing default superadmin...")
        users_collection.insert_one({
            "email": "superadmin@admin.com",
            "password_hash": get_password_hash("admin123"),
            "role": "superadmin",
            "roll_number": "ADMIN000",
            "name": "System Superadmin",
            "is_suspended": False
        })
