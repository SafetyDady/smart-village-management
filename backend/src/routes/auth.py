from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Login endpoint
@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    # Find user by username or email
    user = db.query(models.User).filter(
        (models.User.username == form_data.username) | 
        (models.User.email == form_data.username)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account is locked
    if user.account_locked_until and datetime.utcnow() < user.account_locked_until:
        remaining_time = user.account_locked_until - datetime.utcnow()
        minutes_remaining = int(remaining_time.total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is locked. Try again in {minutes_remaining} minutes.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if user.status != models.UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not auth.verify_password(form_data.password, user.password_hash):
        # Increment login attempts
        user.login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
            db.commit()
            
            # Log security event
            print(f"Account locked for user {user.username} due to multiple failed login attempts")
            
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to multiple failed login attempts. Try again in 30 minutes.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        db.commit()
        
        remaining_attempts = 5 - user.login_attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Incorrect username or password. {remaining_attempts} attempts remaining before account lock.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if email is verified (if email verification is required)
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please verify your email address before logging in",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Reset login attempts on successful login
    user.login_attempts = 0
    user.account_locked_until = None
    user.last_login = datetime.utcnow()
    
    db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={
            "sub": user.username,
            "user_id": str(user.id),
            "village_id": str(user.village_id),
            "role": user.role
        },
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Get current user info
@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return current_user

# Change password
@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: dict,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    # Verify current password
    if not auth.verify_password(password_data["current_password"], current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.password_hash = auth.get_password_hash(password_data["new_password"])
    db.commit()
    
    return {"message": "Password updated successfully"}


# User registration endpoint
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: schemas.UserRegister,
    db: Session = Depends(database.get_db)
):
    # Check if username already exists
    existing_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if village exists
    village = db.query(models.Village).filter(models.Village.id == user_data.village_id).first()
    if not village:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Village not found"
        )
    
    # Create new user
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = models.User(
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone,
        password_hash=hashed_password,
        village_id=user_data.village_id,
        role=models.UserRole.RESIDENT,  # Default role for self-registration
        status=models.UserStatus.ACTIVE,
        email_verified=False,  # Will be verified later
        emergency_contact=user_data.emergency_contact
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token for immediate login
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={
            "sub": db_user.username,
            "user_id": str(db_user.id),
            "village_id": str(db_user.village_id),
            "role": db_user.role
        },
        expires_delta=access_token_expires
    )
    
    # TODO: Send email verification email
    # This will be implemented in Phase 2
    
    return db_user

# Check username availability
@router.get("/check-username/{username}")
async def check_username_availability(
    username: str,
    db: Session = Depends(database.get_db)
):
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    return {"available": existing_user is None}

# Check email availability
@router.get("/check-email/{email}")
async def check_email_availability(
    email: str,
    db: Session = Depends(database.get_db)
):
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    return {"available": existing_user is None}



# Password strength checker endpoint
@router.post("/check-password-strength")
async def check_password_strength(password_data: schemas.PasswordStrengthCheck):
    """Check password strength and provide recommendations"""
    
    password = password_data.password
    score = 0
    feedback = []
    
    # Length check
    if len(password) >= 8:
        score += 2
    elif len(password) >= 6:
        score += 1
        feedback.append("รหัสผ่านควรมีอย่างน้อย 8 ตัวอักษร")
    else:
        feedback.append("รหัสผ่านสั้นเกินไป ควรมีอย่างน้อย 8 ตัวอักษร")
    
    # Character variety checks
    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("ควรมีตัวอักษรพิมพ์เล็ก")
    
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("ควรมีตัวอักษรพิมพ์ใหญ่")
    
    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("ควรมีตัวเลข")
    
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    else:
        feedback.append("ควรมีอักขระพิเศษ")
    
    # Common password patterns
    common_patterns = ["123456", "password", "qwerty", "abc123", "admin"]
    if any(pattern in password.lower() for pattern in common_patterns):
        score -= 2
        feedback.append("หลีกเลี่ยงรหัสผ่านที่ใช้กันทั่วไป")
    
    # Determine strength level
    if score >= 6:
        strength = "strong"
        strength_text = "แข็งแกร่ง"
    elif score >= 4:
        strength = "medium"
        strength_text = "ปานกลาง"
    else:
        strength = "weak"
        strength_text = "อ่อนแอ"
    
    return {
        "strength": strength,
        "strength_text": strength_text,
        "score": max(0, score),
        "max_score": 6,
        "feedback": feedback,
        "is_acceptable": score >= 4
    }

# Get login attempts for a user (admin only)
@router.get("/login-attempts/{user_id}")
async def get_user_login_attempts(
    user_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get login attempts for a specific user (admin only)"""
    
    # Check if current user is admin
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get login attempts for the user
    login_attempts = db.query(models.LoginAttempt).filter(
        models.LoginAttempt.user_id == user_id
    ).order_by(models.LoginAttempt.attempted_at.desc()).limit(50).all()
    
    return {
        "user_id": user_id,
        "login_attempts": [
            {
                "id": attempt.id,
                "ip_address": attempt.ip_address,
                "user_agent": attempt.user_agent,
                "success": attempt.success,
                "attempted_at": attempt.attempted_at,
                "failure_reason": attempt.failure_reason
            }
            for attempt in login_attempts
        ]
    }

# Unlock user account (admin only)
@router.post("/unlock-account/{user_id}")
async def unlock_user_account(
    user_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Unlock a user account (admin only)"""
    
    # Check if current user is admin
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Find the user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Unlock the account
    user.login_attempts = 0
    user.account_locked_until = None
    db.commit()
    
    return {"message": f"Account for user {user.username} has been unlocked"}

# Get security settings for current user
@router.get("/security-settings")
async def get_security_settings(
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get security settings for current user"""
    
    return {
        "user_id": str(current_user.id),
        "email_verified": current_user.email_verified,
        "two_factor_enabled": current_user.two_factor_enabled if hasattr(current_user, 'two_factor_enabled') else False,
        "login_attempts": current_user.login_attempts,
        "account_locked": current_user.account_locked_until is not None and datetime.utcnow() < current_user.account_locked_until,
        "account_locked_until": current_user.account_locked_until,
        "last_login": current_user.last_login,
        "password_changed_at": current_user.password_changed_at if hasattr(current_user, 'password_changed_at') else None
    }

