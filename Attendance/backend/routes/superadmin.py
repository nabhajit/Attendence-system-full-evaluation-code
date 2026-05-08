from fastapi import APIRouter, Depends, HTTPException
from ..database import users_collection
from ..auth_utils import require_role, get_password_hash
from ..models import UserRegister
from bson import ObjectId

router = APIRouter(prefix="/superadmin", tags=["Superadmin Features"])

super_dep = Depends(require_role(["superadmin"]))

@router.post("/admins")
def create_admin(admin_data: UserRegister, user: dict = super_dep):
    if users_collection.find_one({"email": admin_data.email}):
        raise HTTPException(status_code=400, detail="Email already exists")
        
    admin_dict = admin_data.model_dump()
    admin_dict["password_hash"] = get_password_hash(admin_dict.pop("password"))
    admin_dict["role"] = "admin"
    admin_dict["is_suspended"] = False
    
    users_collection.insert_one(admin_dict)
    return {"message": "Admin created successfully"}

@router.get("/users")
def get_all_users(user: dict = super_dep):
    users = list(users_collection.find({}, {"password_hash": 0}))
    for u in users:
        u["_id"] = str(u["_id"])
    return users

@router.patch("/users/{user_id}/suspend")
def suspend_user(user_id: str, is_suspended: bool, user: dict = super_dep):
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_suspended": is_suspended}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    action = "suspended" if is_suspended else "unsuspended"
    return {"message": f"User successfully {action}"}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, user: dict = super_dep):
    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
         raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User permanently deleted"}
