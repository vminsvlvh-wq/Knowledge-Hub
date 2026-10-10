import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from app.db import get_db
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.schemas import UserCreate, UserLogin, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["المصادقة والمستخدمين (Auth)"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_in.email.lower().strip(),))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="البريد الإلكتروني مسجل بالفعل"
            )
        
        user_id = str(uuid.uuid4())
        hashed = hash_password(user_in.password)
        email_clean = user_in.email.lower().strip()
        
        cursor.execute(
            "INSERT INTO users (id, email, full_name, hashed_password) VALUES (?, ?, ?, ?)",
            (user_id, email_clean, user_in.full_name.strip(), hashed)
        )
        
        cursor.execute("SELECT id, email, full_name, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        user_dict = dict(row)
        
    token = create_access_token({"sub": user_id, "email": email_clean})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict
    }

@router.post("/login", response_model=TokenResponse)
def login(login_in: UserLogin):
    email_clean = login_in.email.lower().strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, full_name, hashed_password, created_at FROM users WHERE email = ?",
            (email_clean,)
        )
        row = cursor.fetchone()
        if not row or not verify_password(login_in.password, row["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
            )
        user_dict = {
            "id": row["id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "created_at": row["created_at"]
        }
    
    token = create_access_token({"sub": user_dict["id"], "email": email_clean})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict
    }

@router.get("/me", response_model=UserOut)
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user
