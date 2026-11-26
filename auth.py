import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings
from app.db import get_db
from app.schemas import UserCreate, UserLogin, TokenResponse, UserOut

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

def hash_password(password: str) -> str:
    return _password_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return _password_context.verify(password, hashed_password)

def create_access_token(data: dict) -> str:
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be configured before issuing tokens")
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

def get_current_user(token: str = Depends(_oauth2_scheme)) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="بيانات المصادقة غير صالحة أو منتهية",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_error
    except (JWTError, RuntimeError, TypeError, ValueError):
        raise credentials_error
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id,email,full_name,created_at FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()
    if not user:
        raise credentials_error
    return dict(user)

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
