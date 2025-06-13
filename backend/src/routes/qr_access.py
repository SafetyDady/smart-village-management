from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
import qrcode
import io
import base64
import json

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Generate QR code for visitor
@router.post("/visitors/{visitor_id}/qr-code")
def generate_visitor_qr_code(
    visitor_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get the visitor
    visitor = db.query(models.Visitor).filter(
        models.Visitor.id == visitor_id,
        models.Visitor.village_id == current_user.village_id
    ).first()
    
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )
    
    # For residents, check if they own the property
    if current_user.role == schemas.UserRole.RESIDENT:
        property = db.query(models.Property).filter(
            models.Property.id == visitor.property_id,
            models.Property.owner_id == current_user.id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to generate QR code for this visitor"
            )
    
    # Check if visitor is still valid
    if visitor.valid_until < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor entry has expired"
        )
    
    if visitor.status == schemas.VisitorStatus.USED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor entry has already been used"
        )
    
    # Create QR code data
    qr_data = {
        "visitor_id": str(visitor.id),
        "entry_code": visitor.entry_code,
        "village_id": str(visitor.village_id),
        "property_id": str(visitor.property_id),
        "valid_until": visitor.valid_until.isoformat(),
        "type": "visitor_entry"
    }
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_str = base64.b64encode(img_buffer.getvalue()).decode()
    
    return {
        "qr_code": f"data:image/png;base64,{img_str}",
        "visitor_id": str(visitor.id),
        "entry_code": visitor.entry_code,
        "valid_until": visitor.valid_until.isoformat()
    }

# Verify QR code
@router.post("/qr-verify")
def verify_qr_code(
    qr_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only security staff and admin can verify QR codes
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    try:
        # Parse QR code data
        qr_content = json.loads(qr_data.get("qr_content", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code format"
        )
    
    # Validate QR code type
    if qr_content.get("type") != "visitor_entry":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code type"
        )
    
    # Get visitor
    visitor_id = qr_content.get("visitor_id")
    if not visitor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing visitor ID in QR code"
        )
    
    visitor = db.query(models.Visitor).filter(
        models.Visitor.id == visitor_id,
        models.Visitor.village_id == current_user.village_id
    ).first()
    
    if not visitor:
        return {
            "valid": False,
            "message": "Visitor not found or invalid QR code"
        }
    
    # Verify QR code data matches visitor
    if (qr_content.get("entry_code") != visitor.entry_code or
        qr_content.get("village_id") != str(visitor.village_id) or
        qr_content.get("property_id") != str(visitor.property_id)):
        return {
            "valid": False,
            "message": "QR code data mismatch"
        }
    
    # Check if expired
    valid_until = datetime.fromisoformat(qr_content.get("valid_until", ""))
    if valid_until < datetime.now():
        return {
            "valid": False,
            "message": "QR code has expired",
            "visitor": {
                "id": str(visitor.id),
                "name": visitor.name,
                "property_id": str(visitor.property_id)
            }
        }
    
    # Check if already used
    if visitor.status == schemas.VisitorStatus.USED:
        return {
            "valid": False,
            "message": "QR code has already been used",
            "visitor": {
                "id": str(visitor.id),
                "name": visitor.name,
                "property_id": str(visitor.property_id)
            }
        }
    
    # Mark as used
    visitor.status = schemas.VisitorStatus.USED
    db.commit()
    
    # Create access log
    access_log = models.AccessLog(
        village_id=current_user.village_id,
        property_id=visitor.property_id,
        timestamp=datetime.now(),
        direction=schemas.AccessDirection.ENTRY,
        access_method="qr_code",
        status=schemas.AccessStatus.GRANTED
    )
    
    db.add(access_log)
    db.commit()
    
    # Get property details
    property = db.query(models.Property).filter(models.Property.id == visitor.property_id).first()
    
    return {
        "valid": True,
        "message": "QR code verified successfully",
        "visitor": {
            "id": str(visitor.id),
            "name": visitor.name,
            "property_id": str(visitor.property_id),
            "property_address": property.address if property else None,
            "purpose": visitor.purpose
        }
    }

# Generate QR code for resident gate access
@router.post("/residents/qr-code")
def generate_resident_qr_code(
    property_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only residents can generate their own QR codes
    if current_user.role != schemas.UserRole.RESIDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only residents can generate QR codes"
        )
    
    # Check if user owns or resides in the property
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
    
    # Create QR code data (valid for 5 minutes)
    valid_until = datetime.now() + timedelta(minutes=5)
    qr_data = {
        "user_id": str(current_user.id),
        "property_id": str(property_id),
        "village_id": str(current_user.village_id),
        "valid_until": valid_until.isoformat(),
        "type": "resident_access"
    }
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_str = base64.b64encode(img_buffer.getvalue()).decode()
    
    return {
        "qr_code": f"data:image/png;base64,{img_str}",
        "valid_until": valid_until.isoformat(),
        "property_address": property.address
    }

# Verify resident QR code
@router.post("/residents/qr-verify")
def verify_resident_qr_code(
    qr_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only security staff and admin can verify QR codes
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    try:
        # Parse QR code data
        qr_content = json.loads(qr_data.get("qr_content", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code format"
        )
    
    # Validate QR code type
    if qr_content.get("type") != "resident_access":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code type"
        )
    
    # Check if expired
    try:
        valid_until = datetime.fromisoformat(qr_content.get("valid_until", ""))
        if valid_until < datetime.now():
            return {
                "valid": False,
                "message": "QR code has expired"
            }
    except ValueError:
        return {
            "valid": False,
            "message": "Invalid QR code format"
        }
    
    # Get user and property
    user_id = qr_content.get("user_id")
    property_id = qr_content.get("property_id")
    
    if not user_id or not property_id:
        return {
            "valid": False,
            "message": "Missing required data in QR code"
        }
    
    # Verify user exists and belongs to the village
    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.village_id == current_user.village_id
    ).first()
    
    if not user:
        return {
            "valid": False,
            "message": "User not found"
        }
    
    # Verify property exists and user has access
    property = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not property:
        return {
            "valid": False,
            "message": "Property not found"
        }
    
    # Check authorization
    is_owner = property.owner_id == user.id
    is_resident = False
    if property.resident_ids:
        is_resident = str(user.id) in property.resident_ids
    
    if not (is_owner or is_resident):
        return {
            "valid": False,
            "message": "User not authorized for this property"
        }
    
    # Create access log
    access_log = models.AccessLog(
        village_id=current_user.village_id,
        property_id=property.id,
        user_id=user.id,
        timestamp=datetime.now(),
        direction=schemas.AccessDirection.ENTRY,
        access_method="qr_code",
        status=schemas.AccessStatus.GRANTED
    )
    
    db.add(access_log)
    db.commit()
    
    return {
        "valid": True,
        "message": "QR code verified successfully",
        "user": {
            "id": str(user.id),
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email
        },
        "property": {
            "id": str(property.id),
            "address": property.address
        }
    }

