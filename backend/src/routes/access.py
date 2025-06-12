from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all access logs (filtered by village and permissions)
@router.get("/", response_model=List[schemas.AccessLogResponse])
def get_all_access_logs(
    property_id: UUID = None,
    user_id: UUID = None,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Base query
    query = db.query(models.AccessLog).filter(
        models.AccessLog.village_id == current_user.village_id
    )
    
    # Filter by property_id if provided
    if property_id:
        query = query.filter(models.AccessLog.property_id == property_id)
    
    # Filter by user_id if provided
    if user_id:
        query = query.filter(models.AccessLog.user_id == user_id)
    
    # For residents, only show their own access logs
    if current_user.role == schemas.UserRole.RESIDENT:
        query = query.filter(models.AccessLog.user_id == current_user.id)
    
    # Order by timestamp descending and limit results
    access_logs = query.order_by(models.AccessLog.timestamp.desc()).limit(limit).all()
    
    return access_logs

# Get access log by ID
@router.get("/{log_id}", response_model=schemas.AccessLogResponse)
def get_access_log(
    log_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get the access log
    access_log = db.query(models.AccessLog).filter(models.AccessLog.id == log_id).first()
    
    if not access_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access log not found"
        )
    
    # Check if access log belongs to the user's village
    if access_log.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this log"
        )
    
    # For residents, check if it's their own access log
    if current_user.role == schemas.UserRole.RESIDENT and access_log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this log"
        )
    
    return access_log

# Create new access log (system or admin/staff only)
@router.post("/", response_model=schemas.AccessLogResponse, status_code=status.HTTP_201_CREATED)
def create_access_log(
    log_data: schemas.AccessLogCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can manually create access logs
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if log_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create access log for different village"
        )
    
    # If property_id is provided, check if it exists and belongs to the same village
    if log_data.property_id:
        property = db.query(models.Property).filter(
            models.Property.id == log_data.property_id,
            models.Property.village_id == current_user.village_id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property not found or belongs to different village"
            )
    
    # If user_id is provided, check if user exists and belongs to the same village
    if log_data.user_id:
        user = db.query(models.User).filter(
            models.User.id == log_data.user_id,
            models.User.village_id == current_user.village_id
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found or belongs to different village"
            )
    
    # Create new access log
    db_access_log = models.AccessLog(**log_data.dict())
    
    db.add(db_access_log)
    db.commit()
    db.refresh(db_access_log)
    
    return db_access_log

# Mobile app endpoint for gate access
@router.post("/gate-access", response_model=schemas.AccessLogResponse)
def gate_access(
    access_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get required parameters
    direction = access_data.get("direction")
    property_id = access_data.get("property_id")
    
    if not direction or direction not in [schemas.AccessDirection.ENTRY, schemas.AccessDirection.EXIT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid direction (entry/exit) is required"
        )
    
    # For residents, check if they own or reside in the property
    if current_user.role == schemas.UserRole.RESIDENT and property_id:
        property = db.query(models.Property).filter(
            models.Property.id == property_id,
            models.Property.village_id == current_user.village_id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Check if user is owner or resident
        is_owner = property.owner_id == current_user.id
        is_resident = False
        if property.resident_ids:
            is_resident = str(current_user.id) in property.resident_ids
        
        if not (is_owner or is_resident):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this property"
            )
    
    # Create access log
    access_log = models.AccessLog(
        village_id=current_user.village_id,
        property_id=property_id,
        user_id=current_user.id,
        timestamp=datetime.now(),
        direction=direction,
        access_method="mobile_app",
        status=schemas.AccessStatus.GRANTED
    )
    
    db.add(access_log)
    db.commit()
    db.refresh(access_log)
    
    return access_log

# Get access statistics
@router.get("/statistics", response_model=dict)
def get_access_statistics(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can view statistics
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access statistics"
        )
    
    # Parse dates if provided
    start_datetime = None
    end_datetime = None
    
    if start_date:
        try:
            start_datetime = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format"
            )
    
    if end_date:
        try:
            end_datetime = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format"
            )
    
    # Base query
    query = db.query(models.AccessLog).filter(
        models.AccessLog.village_id == current_user.village_id
    )
    
    # Apply date filters if provided
    if start_datetime:
        query = query.filter(models.AccessLog.timestamp >= start_datetime)
    
    if end_datetime:
        query = query.filter(models.AccessLog.timestamp <= end_datetime)
    
    # Get all matching logs
    logs = query.all()
    
    # Calculate statistics
    total_entries = sum(1 for log in logs if log.direction == schemas.AccessDirection.ENTRY)
    total_exits = sum(1 for log in logs if log.direction == schemas.AccessDirection.EXIT)
    
    # Count by access method
    access_methods = {}
    for log in logs:
        if log.access_method not in access_methods:
            access_methods[log.access_method] = 0
        access_methods[log.access_method] += 1
    
    # Count by status
    status_counts = {
        "granted": sum(1 for log in logs if log.status == schemas.AccessStatus.GRANTED),
        "denied": sum(1 for log in logs if log.status == schemas.AccessStatus.DENIED)
    }
    
    return {
        "total_logs": len(logs),
        "entries": total_entries,
        "exits": total_exits,
        "by_access_method": access_methods,
        "by_status": status_counts
    }
