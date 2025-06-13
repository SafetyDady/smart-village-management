from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from uuid import UUID
from datetime import datetime, timedelta
import random
import string

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Simulate hardware gate control
@router.post("/gate/control")
def control_gate(
    gate_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Simulate hardware gate control
    Expected gate_data: {
        "action": "open" | "close",
        "gate_id": "main_gate" | "secondary_gate",
        "user_id": UUID (optional),
        "property_id": UUID (optional)
    }
    """
    
    # Only authorized users can control gates
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF, schemas.UserRole.RESIDENT]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control gates"
        )
    
    action = gate_data.get("action")
    gate_id = gate_data.get("gate_id", "main_gate")
    user_id = gate_data.get("user_id")
    property_id = gate_data.get("property_id")
    
    if action not in ["open", "close"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action. Must be 'open' or 'close'"
        )
    
    # For residents, verify they have access to the property
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
        
        # Check authorization
        is_owner = property.owner_id == current_user.id
        is_resident = False
        if property.resident_ids:
            is_resident = str(current_user.id) in property.resident_ids
        
        if not (is_owner or is_resident):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this property"
            )
    
    # Check gate operation mode
    # Get the effective operation mode for this gate
    now = datetime.now()
    current_day = now.weekday()
    current_time = now.time()
    
    # Check for active override
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id,
        models.GateOverride.expiry_time > now
    ).first()
    
    if db_override:
        operation_mode = db_override.operation_mode
    else:
        # Check for active schedule
        active_schedule = db.query(models.GateSchedule).filter(
            models.GateSchedule.village_id == current_user.village_id,
            models.GateSchedule.gate_id == gate_id,
            models.GateSchedule.days_of_week.contains([current_day]),
            models.GateSchedule.start_time <= current_time,
            models.GateSchedule.end_time > current_time
        ).first()
        
        if active_schedule:
            operation_mode = active_schedule.operation_mode
        else:
            # Default mode
            operation_mode = "staff_assisted"
    
    # If in staff_assisted mode, only staff and admin can control gates directly
    if operation_mode == "staff_assisted" and current_user.role == schemas.UserRole.RESIDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gate is in staff-assisted mode. Please contact security staff for access."
        )
    
    # Simulate gate operation
    operation_success = True  # In real implementation, this would interface with actual hardware
    
    if operation_success:
        # Log the gate operation
        access_log = models.AccessLog(
            village_id=current_user.village_id,
            property_id=property_id,
            user_id=user_id or current_user.id,
            timestamp=datetime.now(),
            direction=schemas.AccessDirection.ENTRY if action == "open" else schemas.AccessDirection.EXIT,
            access_method="gate_control",
            status=schemas.AccessStatus.GRANTED
        )
        
        db.add(access_log)
        db.commit()
        
        return {
            "success": True,
            "message": f"Gate {gate_id} {action}ed successfully",
            "gate_id": gate_id,
            "action": action,
            "operation_mode": operation_mode,
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "success": False,
            "message": f"Failed to {action} gate {gate_id}",
            "gate_id": gate_id,
            "action": action
        }

# Get gate status
@router.get("/gate/status")
def get_gate_status(
    gate_id: str = "main_gate",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get current gate status (simulated)
    """
    
    # Get the effective operation mode for this gate
    now = datetime.now()
    current_day = now.weekday()
    current_time = now.time()
    
    # Check for active override
    db_override = db.query(models.GateOverride).filter(
        models.GateOverride.village_id == current_user.village_id,
        models.GateOverride.gate_id == gate_id,
        models.GateOverride.expiry_time > now
    ).first()
    
    if db_override:
        operation_mode = db_override.operation_mode
        mode_source = "override"
        mode_expiry = db_override.expiry_time.isoformat()
    else:
        # Check for active schedule
        active_schedule = db.query(models.GateSchedule).filter(
            models.GateSchedule.village_id == current_user.village_id,
            models.GateSchedule.gate_id == gate_id,
            models.GateSchedule.days_of_week.contains([current_day]),
            models.GateSchedule.start_time <= current_time,
            models.GateSchedule.end_time > current_time
        ).first()
        
        if active_schedule:
            operation_mode = active_schedule.operation_mode
            mode_source = "schedule"
            mode_expiry = None
        else:
            # Default mode
            operation_mode = "staff_assisted"
            mode_source = "default"
            mode_expiry = None
    
    # Simulate gate status
    gate_statuses = {
        "main_gate": {
            "id": "main_gate",
            "name": "Main Gate",
            "status": "closed",  # "open" | "closed" | "maintenance"
            "last_operation": datetime.now() - timedelta(minutes=15),
            "operational": True
        },
        "secondary_gate": {
            "id": "secondary_gate", 
            "name": "Secondary Gate",
            "status": "closed",
            "last_operation": datetime.now() - timedelta(hours=2),
            "operational": True
        }
    }
    
    if gate_id not in gate_statuses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gate not found"
        )
    
    # Add operation mode information to the response
    gate_status = gate_statuses[gate_id]
    gate_status["operation_mode"] = operation_mode
    gate_status["mode_source"] = mode_source
    gate_status["mode_expiry"] = mode_expiry
    
    return gate_status

# Simulate RFID card scanning
@router.post("/rfid/scan")
def scan_rfid_card(
    rfid_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Simulate RFID card scanning
    Expected rfid_data: {
        "card_id": "string",
        "gate_id": "main_gate" | "secondary_gate"
    }
    """
    
    # Only security staff and admin can process RFID scans
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process RFID scans"
        )
    
    card_id = rfid_data.get("card_id")
    gate_id = rfid_data.get("gate_id", "main_gate")
    
    if not card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card ID is required"
        )
    
    # In a real implementation, you would look up the card_id in a database
    # For simulation, we'll create some mock card data
    mock_cards = {
        "CARD001": {
            "user_id": None,  # Would be actual user ID
            "property_id": None,  # Would be actual property ID
            "name": "John Doe",
            "access_level": "resident",
            "active": True
        },
        "CARD002": {
            "user_id": None,
            "property_id": None,
            "name": "Jane Smith", 
            "access_level": "staff",
            "active": True
        }
    }
    
    card_info = mock_cards.get(card_id)
    
    if not card_info:
        # Log failed access attempt
        access_log = models.AccessLog(
            village_id=current_user.village_id,
            timestamp=datetime.now(),
            direction=schemas.AccessDirection.ENTRY,
            access_method="rfid_card",
            status=schemas.AccessStatus.DENIED
        )
        
        db.add(access_log)
        db.commit()
        
        return {
            "valid": False,
            "message": "Invalid or unregistered RFID card",
            "card_id": card_id
        }
    
    if not card_info["active"]:
        return {
            "valid": False,
            "message": "RFID card is deactivated",
            "card_id": card_id
        }
    
    # Log successful access
    access_log = models.AccessLog(
        village_id=current_user.village_id,
        property_id=card_info["property_id"],
        user_id=card_info["user_id"],
        timestamp=datetime.now(),
        direction=schemas.AccessDirection.ENTRY,
        access_method="rfid_card",
        status=schemas.AccessStatus.GRANTED
    )
    
    db.add(access_log)
    db.commit()
    
    return {
        "valid": True,
        "message": "RFID card verified successfully",
        "card_id": card_id,
        "user_name": card_info["name"],
        "access_level": card_info["access_level"],
        "gate_id": gate_id
    }

# Get real-time access monitoring
@router.get("/monitoring/realtime")
def get_realtime_monitoring(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get real-time access monitoring data
    """
    
    # Only admin and staff can view monitoring data
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view monitoring data"
        )
    
    # Get recent access logs (last 24 hours)
    since = datetime.now() - timedelta(hours=24)
    recent_logs = db.query(models.AccessLog).filter(
        models.AccessLog.village_id == current_user.village_id,
        models.AccessLog.timestamp >= since
    ).order_by(models.AccessLog.timestamp.desc()).limit(50).all()
    
    # Get current gate statuses
    gate_statuses = [
        {
            "id": "main_gate",
            "name": "Main Gate",
            "status": "closed",
            "operational": True,
            "last_activity": datetime.now() - timedelta(minutes=15)
        },
        {
            "id": "secondary_gate",
            "name": "Secondary Gate", 
            "status": "closed",
            "operational": True,
            "last_activity": datetime.now() - timedelta(hours=2)
        }
    ]
    
    # Calculate statistics
    total_entries = sum(1 for log in recent_logs if log.direction == schemas.AccessDirection.ENTRY)
    total_exits = sum(1 for log in recent_logs if log.direction == schemas.AccessDirection.EXIT)
    denied_attempts = sum(1 for log in recent_logs if log.status == schemas.AccessStatus.DENIED)
    
    # Group by access method
    access_methods = {}
    for log in recent_logs:
        method = log.access_method or "unknown"
        if method not in access_methods:
            access_methods[method] = 0
        access_methods[method] += 1
    
    return {
        "timestamp": datetime.now().isoformat(),
        "gates": gate_statuses,
        "recent_activity": [
            {
                "id": str(log.id),
                "timestamp": log.timestamp.isoformat(),
                "direction": log.direction,
                "access_method": log.access_method,
                "status": log.status,
                "property_id": str(log.property_id) if log.property_id else None,
                "user_id": str(log.user_id) if log.user_id else None
            }
            for log in recent_logs[:10]  # Last 10 activities
        ],
        "statistics": {
            "total_entries_24h": total_entries,
            "total_exits_24h": total_exits,
            "denied_attempts_24h": denied_attempts,
            "by_access_method": access_methods
        }
    }

# Security alerts endpoint
@router.get("/security/alerts")
def get_security_alerts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get security alerts and suspicious activities
    """
    
    # Only admin and staff can view security alerts
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view security alerts"
        )
    
    # Get recent denied access attempts
    since = datetime.now() - timedelta(hours=24)
    denied_attempts = db.query(models.AccessLog).filter(
        models.AccessLog.village_id == current_user.village_id,
        models.AccessLog.timestamp >= since,
        models.AccessLog.status == schemas.AccessStatus.DENIED
    ).order_by(models.AccessLog.timestamp.desc()).all()
    
    # Generate alerts based on patterns
    alerts = []
    
    # Alert for multiple denied attempts
    if len(denied_attempts) > 5:
        alerts.append({
            "id": "multiple_denied_attempts",
            "type": "security",
            "severity": "medium",
            "message": f"{len(denied_attempts)} denied access attempts in the last 24 hours",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "count": len(denied_attempts),
                "timeframe": "24 hours"
            }
        })
    
    # Alert for unusual access patterns (example: access outside normal hours)
    unusual_hours = [log for log in denied_attempts if log.timestamp.hour < 6 or log.timestamp.hour > 22]
    if unusual_hours:
        alerts.append({
            "id": "unusual_hours_access",
            "type": "security",
            "severity": "low",
            "message": f"{len(unusual_hours)} access attempts outside normal hours",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "count": len(unusual_hours),
                "description": "Access attempts between 10 PM and 6 AM"
            }
        })
    
    return {
        "alerts": alerts,
        "total_alerts": len(alerts),
        "last_updated": datetime.now().isoformat()
    }

