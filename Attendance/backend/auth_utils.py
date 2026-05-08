import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from . import env_loader
from .database import users_collection
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    print("🚨 CRITICAL WARNING: JWT_SECRET_KEY is not set in .env! Using insecure fallback key. Passwords and sessions are at risk!")
    SECRET_KEY = "fallback_secret_key"
    
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = users_collection.find_one({"email": email})
    if user is None:
        raise HTTPException(status_code=401, detail="User non-existent")
    if user.get("is_suspended", False):
        raise HTTPException(status_code=403, detail="User account is suspended")
    
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "roll_number": user.get("roll_number"),
        "name": user.get("name")
    }

def require_role(roles: list):
    def role_checker(current_user: dict = Security(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker
