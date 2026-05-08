import os
import pymongo
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MongoDatabaseManager:
    _instance = None
    _client = None

    def __new__(cls):
        # Singleton pattern for connection pooling
        if cls._instance is None:
            cls._instance = super(MongoDatabaseManager, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self):
        """Initializes the MongoDB connection and ensures collections/indices are set up."""
        try:
            # Fallback to local if no URI is provided, useful if the .env string isn't substituted
            mongo_uri =os.getenv("MONGO_URI")
            db_name = os.getenv("DB_NAME", "smart_attendance_db")

            self._client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self._client[db_name]
            
            # Create collections explicitly
            self.students = self.db["students"]
            self.attendance = self.db["attendance"]

            # Set up scalable indexing
            # Student collection: enforce unique roll numbers (names can have duplicates)
            self.students.create_index("roll", unique=True)
            # Remove unique constraint from name if it exists (allows duplicates)
            try:
                # We don't strictly drop it here to avoid errors if it doesn't exist, 
                # but ensure we don't rely on it for uniqueness anymore.
                self.students.drop_index("name_1")
            except:
                pass
            
            # Attendance collection: optimize daily queries per person
            # Optimized for "Has student X already been marked for date Y?"
            try:
                # Drop the old inefficient index if it exists
                self.attendance.drop_index("date_-1_roll_1")
            except:
                pass

            self.attendance.create_index(
                [("roll", pymongo.ASCENDING), ("date", pymongo.DESCENDING)]
            )
            
            print(f"Success: Securely connected to MongoDB (Database: {db_name}).")
        except pymongo.errors.ServerSelectionTimeoutError as err:
            print(f"Error: Failed to connect to MongoDB. Is the cluster URI correct? Error: {err}")
        except Exception as e:
            print(f"Error: MongoDB Initialization error: {e}")

    def add_student(self, name, student_class, roll, contact="", cloudinary_urls=None, embedding=None, course=""):
        """Add a new student document to the database."""
        try:
            student_data = {
                "name": name,
                "class": student_class,
                "roll": roll,
                "contact": contact,
                "course": course,
                "enrolled_at": datetime.now()
            }
            
            update_op = {"$setOnInsert": student_data}
            
            # If we're updating with arrays/lists right at registration or future capture
            if cloudinary_urls or embedding:
                set_op = {}
                if cloudinary_urls:
                    set_op["cloudinary_urls"] = cloudinary_urls
                if embedding:
                    set_op["embedding"] = embedding
                update_op["$set"] = set_op
                
            # Instead of throwing exceptions on duplicates we use update with upset
            # We now use 'roll' as the unique identifier for students
            result = self.students.update_one(
                {"roll": roll},
                update_op,
                upsert=True
            )
            
            if result.upserted_id:
                return True
            else:
                # If matched_count > 0, it means the student by roll already exists
                # In that case, we might have updated the embedding or cloudinary_urls
                return result.matched_count > 0
        except Exception as e:
            print(f"Error: Adding student to MongoDB: {e}")
            return False

    def update_student(self, roll, student_class, name, contact):
        """Update an existing student's details using roll as unique key."""
        try:
            result = self.students.update_one(
                {"roll": roll},
                {"$set": {
                    "class": student_class,
                    "name": name,
                    "contact": contact,
                    "last_updated": datetime.now()
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error: Updating student in MongoDB: {e}")
            return False

    def mark_attendance(self, roll, name=None, status="Present", confidence=None, course_code="Unknown", section="Unknown"):
        """Mark attendance for a student (avoids duplicates for same day + class using roll and course_code)."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        try:
            # If name is not provided, fetch it from students collection to maintain consistency
            if not name:
                student = self.students.find_one({"roll": roll}, {"name": 1})
                if student:
                    name = student.get("name")
                else:
                    print(f"⚠️ Cannot mark attendance: Roll '{roll}' not found.")
                    return False

            # Check if this student already marked for today in this SPECIFIC class
            existing_record = self.attendance.find_one({
                "roll": roll,
                "date": current_date,
                "course_code": course_code,
                "section": section
            })

            if existing_record:
                return False  # Already marked for this specific class today
                
            # Insert the new record
            attendance_record = {
                "roll": roll,
                "student_name": name, # We still keep name for easy viewing
                "course_code": course_code,
                "section": section,
                "date": current_date,
                "time": current_time,
                "status": status,
                "confidence": confidence,  # Store the biometric score
                "timestamp": datetime.now()
            }
            self.attendance.insert_one(attendance_record)
            return True
        except Exception as e:
            print(f"Error: Marking attendance in MongoDB: {e}")
            return False

    def get_student_details(self, roll):
        """Retrieve student details by roll number (unique)."""
        try:
            doc = self.students.find_one({"roll": roll})
            if doc:
                # Return standard tuple pattern: (id placeholder, name, class, roll, contact)
                return (str(doc["_id"]), doc.get("name"), doc.get("class", "Unknown"), doc.get("roll", "N/A"), doc.get("contact", "N/A"))
            return None
        except Exception as e:
            print(f"Error: Fetching student from MongoDB: {e}")
            return False

    def get_all_students(self):
        """Retrieve all students (used for rebuilding database vectors)."""
        try:
            return list(self.students.find({}))
        except Exception as e:
            print(f"Error: Fetching all students from MongoDB: {e}")
            return []

    def get_attendance_log(self, specific_date=None):
        """Retrieve attendance records, joining with student details."""
        try:
            pipeline = [
                {
                    "$lookup": {
                        "from": "students",
                        "localField": "roll",
                        "foreignField": "roll",
                        "as": "student_info"
                    }
                },
                {"$unwind": {"path": "$student_info", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        "_id": 0,
                        "Name": "$student_name",
                        "Class": {"$ifNull": ["$student_info.class", "Unknown"]},
                        "Roll": {"$ifNull": ["$student_info.roll", "N/A"]},
                        "Date": "$date",
                        "Time": "$time",
                        "Status": {"$ifNull": ["$status", "Present"]}
                    }
                },
                {"$sort": {"Date": -1, "Time": -1}}
            ]
            
            if specific_date:
                # Pre-filter before the lookup for performance 
                pipeline.insert(0, {"$match": {"date": specific_date}})
                
            results = list(self.attendance.aggregate(pipeline))
            return results
        except Exception as e:
            print(f"Error: Fetching attendance log from MongoDB: {e}")
            return []
