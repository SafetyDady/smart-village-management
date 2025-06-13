from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import uuid

from ... import schemas, database
from ...models import models
from ...utils import auth

router = APIRouter()

# Self-registration endpoint
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: schemas.UserRegister,
    db: Session = Depends(database.get_db)
):
    # Check if username already exists
    existing_username = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_username:
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
    
    # Create new user with RESIDENT role by default
    hashed_password = auth.get_password_hash(user_data.password)
    
    # Create user object
    db_user = models.User(
        village_id=user_data.village_id,
        role=schemas.UserRole.RESIDENT,  # Default role for self-registration
        username=user_data.username,
        password_hash=hashed_password,
        email=user_data.email,
        phone=user_data.phone,
        status=schemas.UserStatus.ACTIVE,  # Set to ACTIVE by default, can be changed to PENDING if email verification is required
        email_verified=False,  # New field, needs to be added to the User model
        profile_image=None,
        emergency_contact=user_data.emergency_contact if hasattr(user_data, 'emergency_contact') else None
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Generate email verification token and send verification email
    # This will be implemented in the email verification phase
    
    return db_user
