from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Attendence.backend.database import init_db

# Import routers
from .routes import auth, student, admin, superadmin, faculty
from .routes import face_register, video
app = FastAPI(
    title="Smart Attendance Backend API",
    description="A robust RBAC backend for the physical face attendance system.",
    version="1.0.0"
)

# CORS config to allow frontend React/Next.js apps to connect securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, change to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    print("🚀 Database connections verified and initialized.")

# Included routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(admin.router)
app.include_router(superadmin.router)
app.include_router(faculty.router)
app.include_router(face_register.router)
app.include_router(video.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Attendance API!"}
