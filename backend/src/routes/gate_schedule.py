from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, time, timedelta
import json

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all gate schedules
@router.get("/", response_model=List[schemas.GateScheduleResponse])
def get_all_gate_schedules(
    gate_id: str = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get all gate operation schedules for the village
    """
    # Only admin and staff can view all schedules
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view gate schedules"
        )
    
    # Base query
    query = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id
    )
    
    # Filter by gate_id if provided
    if gate_id:
        query = query.filter(models.GateSchedule.gate_id == gate_id)
    
    # Order by start_time
    schedules = query.order_by(models.GateSchedule.start_time).all()
    
    return schedules

# Get gate schedule by ID
@router.get("/{schedule_id}", response_model=schemas.GateScheduleResponse)
def get_gate_schedule(
    schedule_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get a specific gate schedule by ID
    """
    # Only admin and staff can view schedules
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view gate schedules"
        )
    
    # Get the schedule
    schedule = db.query(models.GateSchedule).filter(
        models.GateSchedule.id == schedule_id,
        models.GateSchedule.village_id == current_user.village_id
    ).first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate schedule not found"
        )
    
    return schedule

# Create new gate schedule
@router.post("/", response_model=schemas.GateScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_gate_schedule(
    schedule_data: schemas.GateScheduleCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Create a new gate operation schedule
    """
    # Only admin can create schedules
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create gate schedules"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if schedule_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create schedule for different village"
        )
    
    # Validate time range
    if schedule_data.start_time >= schedule_data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )
    
    # Check for overlapping schedules for the same gate
    overlapping_schedules = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == schedule_data.gate_id,
        models.GateSchedule.days_of_week.overlap(schedule_data.days_of_week),
        models.GateSchedule.start_time < schedule_data.end_time,
        models.GateSchedule.end_time > schedule_data.start_time
    ).all()
    
    if overlapping_schedules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule overlaps with existing schedules for this gate"
        )
    
    # Create new schedule
    db_schedule = models.GateSchedule(**schedule_data.dict())
    
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    return db_schedule

# Update gate schedule
@router.put("/{schedule_id}", response_model=schemas.GateScheduleResponse)
def update_gate_schedule(
    schedule_id: UUID,
    schedule_update: schemas.GateScheduleUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Update an existing gate schedule
    """
    # Only admin can update schedules
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update gate schedules"
        )
    
    # Get the schedule
    db_schedule = db.query(models.GateSchedule).filter(
        models.GateSchedule.id == schedule_id,
        models.GateSchedule.village_id == current_user.village_id
    ).first()
    
    if not db_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate schedule not found"
        )
    
    # Update schedule fields
    update_data = schedule_update.dict(exclude_unset=True)
    
    # If updating time range, validate it
    if "start_time" in update_data or "end_time" in update_data:
        new_start_time = update_data.get("start_time", db_schedule.start_time)
        new_end_time = update_data.get("end_time", db_schedule.end_time)
        
        if new_start_time >= new_end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time"
            )
    
    # If updating days or time, check for overlaps
    if "days_of_week" in update_data or "start_time" in update_data or "end_time" in update_data or "gate_id" in update_data:
        new_days = update_data.get("days_of_week", db_schedule.days_of_week)
        new_start_time = update_data.get("start_time", db_schedule.start_time)
        new_end_time = update_data.get("end_time", db_schedule.end_time)
        new_gate_id = update_data.get("gate_id", db_schedule.gate_id)
        
        overlapping_schedules = db.query(models.GateSchedule).filter(
            models.GateSchedule.village_id == current_user.village_id,
            models.GateSchedule.gate_id == new_gate_id,
            models.GateSchedule.id != schedule_id,  # Exclude current schedule
            models.GateSchedule.days_of_week.overlap(new_days),
            models.GateSchedule.start_time < new_end_time,
            models.GateSchedule.end_time > new_start_time
        ).all()
        
        if overlapping_schedules:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated schedule would overlap with existing schedules"
            )
    
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    db.commit()
    db.refresh(db_schedule)
    
    return db_schedule

# Delete gate schedule
@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gate_schedule(
    schedule_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Delete a gate schedule
    """
    # Only admin can delete schedules
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete gate schedules"
        )
    
    # Get the schedule
    db_schedule = db.query(models.GateSchedule).filter(
        models.GateSchedule.id == schedule_id,
        models.GateSchedule.village_id == current_user.village_id
    ).first()
    
    if not db_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate schedule not found"
        )
    
    db.delete(db_schedule)
    db.commit()
    
    return None

# Get current gate operation mode
@router.get("/gates/{gate_id}/mode", response_model=dict)
def get_gate_operation_mode(
    gate_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get the current operation mode for a specific gate based on schedules
    """
    # Check if gate exists (in a real implementation, you would have a Gate model)
    # For now, we'll just check if there are any schedules for this gate
    gate_exists = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id
    ).first() is not None
    
    if not gate_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found"
        )
    
    # Get current time and day of week
    now = datetime.now()
    current_day = now.weekday()  # 0 = Monday, 6 = Sunday
    current_time = now.time()
    
    # Find active schedule for current time
    active_schedule = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id,
        models.GateSchedule.days_of_week.contains([current_day]),
        models.GateSchedule.start_time <= current_time,
        models.GateSchedule.end_time > current_time
    ).first()
    
    if active_schedule:
        return {
            "gate_id": gate_id,
            "current_mode": active_schedule.operation_mode,
            "schedule_id": str(active_schedule.id),
            "start_time": active_schedule.start_time.isoformat(),
            "end_time": active_schedule.end_time.isoformat(),
            "timestamp": now.isoformat()
        }
    else:
        # Default mode when no schedule is active
        return {
            "gate_id": gate_id,
            "current_mode": "staff_assisted",  # Default to staff-assisted mode
            "schedule_id": None,
            "timestamp": now.isoformat()
        }

# Override gate operation mode temporarily
@router.post("/gates/{gate_id}/override", response_model=dict)
def override_gate_operation_mode(
    gate_id: str,
    override_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Override the gate operation mode temporarily
    """
    # Only admin and staff can override gate mode
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to override gate operation mode"
        )
    
    # Check if gate exists (in a real implementation, you would have a Gate model)
    # For now, we'll just check if there are any schedules for this gate
    gate_exists = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id
    ).first() is not None
    
    if not gate_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found"
        )
    
    # Get override parameters
    operation_mode = override_data.get("operation_mode")
    duration_minutes = override_data.get("duration_minutes", 60)  # Default to 1 hour
    
    if operation_mode not in ["staff_assisted", "automated"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operation mode. Must be 'staff_assisted' or 'automated'"
        )
    
    if duration_minutes <= 0 or duration_minutes > 1440:  # Max 24 hours
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration must be between 1 and 1440 minutes (24 hours)"
        )
    
    # Calculate expiry time
    now = datetime.now()
    expiry_time = now + timedelta(minutes=duration_minutes)
    
    # Create or update override record
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id
    ).first()
    
    if db_override:
        # Update existing override
        db_override.operation_mode = operation_mode
        db_override.expiry_time = expiry_time
        db_override.created_by = current_user.id
    else:
        # Create new override
        db_override = models.GateOverride(
            village_id=current_user.village_id,
            gate_id=gate_id,
            operation_mode=operation_mode,
            expiry_time=expiry_time,
            created_by=current_user.id
        )
        db.add(db_override)
    
    db.commit()
    db.refresh(db_override)
    
    return {
        "gate_id": gate_id,
        "operation_mode": operation_mode,
        "expiry_time": expiry_time.isoformat(),
        "duration_minutes": duration_minutes,
        "created_by": str(current_user.id)
    }

# Clear gate operation mode override
@router.delete("/gates/{gate_id}/override", status_code=status.HTTP_204_NO_CONTENT)
def clear_gate_operation_mode_override(
    gate_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Clear any temporary override for gate operation mode
    """
    # Only admin and staff can clear overrides
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to clear gate operation mode override"
        )
    
    # Find and delete override
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id
    ).first()
    
    if db_override:
        db.delete(db_override)
        db.commit()
    
    return None

# Get gate operation mode with override consideration
@router.get("/gates/{gate_id}/effective-mode", response_model=dict)
def get_effective_gate_operation_mode(
    gate_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get the effective operation mode for a gate, considering both schedules and overrides
    """
    # Check if gate exists (in a real implementation, you would have a Gate model)
    # For now, we'll just check if there are any schedules for this gate
    gate_exists = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id
    ).first() is not None
    
    if not gate_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found"
        )
    
    # Check for active override
    now = datetime.now()
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id,
        models.GateOverride.expiry_time > now
    ).first()
    
    if db_override:
        # Override is active
        return {
            "gate_id": gate_id,
            "effective_mode": db_override.operation_mode,
            "source": "override",
            "expiry_time": db_override.expiry_time.isoformat(),
            "created_by": str(db_override.created_by),
            "timestamp": now.isoformat()
        }
    
    # No override, check schedule
    current_day = now.weekday()
    current_time = now.time()
    
    active_schedule = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id,
        models.GateSchedule.days_of_week.contains([current_day]),
        models.GateSchedule.start_time <= current_time,
        models.GateSchedule.end_time > current_time
    ).first()
    
    if active_schedule:
        return {
            "gate_id": gate_id,
            "effective_mode": active_schedule.operation_mode,
            "source": "schedule",
            "schedule_id": str(active_schedule.id),
            "start_time": active_schedule.start_time.isoformat(),
            "end_time": active_schedule.end_time.isoformat(),
            "timestamp": now.isoformat()
        }
    else:
        # Default mode when no schedule is active
        return {
            "gate_id": gate_id,
            "effective_mode": "staff_assisted",  # Default to staff-assisted mode
            "source": "default",
            "timestamp": now.isoformat()
        }

# Get next scheduled mode change
@router.get("/gates/{gate_id}/next-change", response_model=dict)
def get_next_gate_mode_change(
    gate_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get information about the next scheduled mode change for a gate
    """
    # Check if gate exists
    gate_exists = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id
    ).first() is not None
    
    if not gate_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found"
        )
    
    now = datetime.now()
    current_day = now.weekday()
    current_time = now.time()
    
    # First, check for active override
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id,
        models.GateOverride.expiry_time > now
    ).first()
    
    # Get all schedules for this gate
    all_schedules = db.query(models.GateSchedule).filter(
        models.GateSchedule.village_id == current_user.village_id,
        models.GateSchedule.gate_id == gate_id
    ).all()
    
    if not all_schedules:
        return {
            "gate_id": gate_id,
            "has_next_change": False,
            "message": "No schedules configured for this gate"
        }
    
    # Find the next schedule change
    next_change = None
    days_until_next = 7  # Maximum days to look ahead
    
    # Check for schedule changes today
    today_schedules = [s for s in all_schedules if current_day in s.days_of_week]
    for schedule in today_schedules:
        if schedule.start_time > current_time:
            # This schedule starts later today
            next_datetime = datetime.combine(now.date(), schedule.start_time)
            days_until = 0
            if not next_change or next_datetime < next_change["datetime"]:
                next_change = {
                    "datetime": next_datetime,
                    "schedule": schedule,
                    "days_until": days_until,
                    "type": "start"
                }
        
        if schedule.end_time > current_time:
            # This schedule ends later today
            next_datetime = datetime.combine(now.date(), schedule.end_time)
            days_until = 0
            if not next_change or next_datetime < next_change["datetime"]:
                next_change = {
                    "datetime": next_datetime,
                    "schedule": schedule,
                    "days_until": days_until,
                    "type": "end"
                }
    
    # If no changes today, look ahead for the next few days
    if not next_change:
        for days_ahead in range(1, 8):  # Look up to a week ahead
            check_day = (current_day + days_ahead) % 7
            day_schedules = [s for s in all_schedules if check_day in s.days_of_week]
            
            if day_schedules:
                # Find earliest start time for that day
                earliest_schedule = min(day_schedules, key=lambda s: s.start_time)
                next_date = now.date() + timedelta(days=days_ahead)
                next_datetime = datetime.combine(next_date, earliest_schedule.start_time)
                
                next_change = {
                    "datetime": next_datetime,
                    "schedule": earliest_schedule,
                    "days_until": days_ahead,
                    "type": "start"
                }
                break
    
    # Format response
    if db_override and (not next_change or db_override.expiry_time < next_change["datetime"]):
        # Override expiry is the next change
        return {
            "gate_id": gate_id,
            "has_next_change": True,
            "next_change_type": "override_expiry",
            "current_mode": db_override.operation_mode,
            "next_mode": "scheduled",  # Will revert to scheduled mode
            "change_time": db_override.expiry_time.isoformat(),
            "timestamp": now.isoformat()
        }
    elif next_change:
        # Schedule change is next
        if next_change["type"] == "start":
            next_mode = next_change["schedule"].operation_mode
            change_type = "schedule_start"
        else:  # end
            # When a schedule ends, find what mode comes next
            # This could be another schedule or default mode
            next_day = next_change["datetime"].weekday()
            next_time = next_change["schedule"].end_time
            
            # Check if another schedule starts immediately
            next_schedule = db.query(models.GateSchedule).filter(
                models.GateSchedule.village_id == current_user.village_id,
                models.GateSchedule.gate_id == gate_id,
                models.GateSchedule.days_of_week.contains([next_day]),
                models.GateSchedule.start_time == next_time
            ).first()
            
            if next_schedule:
                next_mode = next_schedule.operation_mode
            else:
                next_mode = "staff_assisted"  # Default mode
            
            change_type = "schedule_end"
        
        return {
            "gate_id": gate_id,
            "has_next_change": True,
            "next_change_type": change_type,
            "current_schedule_id": str(next_change["schedule"].id) if next_change["type"] == "end" else None,
            "next_schedule_id": str(next_change["schedule"].id) if next_change["type"] == "start" else None,
            "next_mode": next_mode,
            "change_time": next_change["datetime"].isoformat(),
            "days_until": next_change["days_until"],
            "timestamp": now.isoformat()
        }
    else:
        return {
            "gate_id": gate_id,
            "has_next_change": False,
            "message": "No upcoming mode changes scheduled",
            "timestamp": now.isoformat()
        }

