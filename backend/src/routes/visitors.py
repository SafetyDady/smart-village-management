from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
import random
import string

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all visitors (filtered by village and property)
@router.get("/", response_model=List[schemas.VisitorResponse])
def get_all_visitors(
    property_id: UUID = None,
    status: str = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Base query
    query = db.query(models.Visitor).filter(
        models.Visitor.village_id == current_user.village_id
    )
    
    # Filter by property_id if provided
    if property_id:
        query = query.filter(models.Visitor.property_id == property_id)
    
    # Filter by status if provided
    if status and status in [schemas.VisitorStatus.PENDING, schemas.VisitorStatus.USED, schemas.VisitorStatus.EXPIRED]:
        query = query.filter(models.Visitor.status == status)
    
    # For residents, only show their own property's visitors
    if current_user.role == schemas.UserRole.RESIDENT:
        # Get properties owned by the user
        properties = db.query(models.Property).filter(
            models.Property.owner_id == current_user.id,
            models.Property.village_id == current_user.village_id
        ).all()
        
        property_ids = [prop.id for prop in properties]
        
        query = query.filter(models.Visitor.property_id.in_(property_ids))
    
    # Order by valid_until descending
    visitors = query.order_by(models.Visitor.valid_until.desc()).all()
    
    return visitors

# Get visitor by ID
@router.get("/{visitor_id}", response_model=schemas.VisitorResponse)
def get_visitor(
    visitor_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get the visitor
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )
    
    # Check if visitor belongs to the user's village
    if visitor.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this visitor"
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
                detail="Not authorized to access this visitor"
            )
    
    return visitor

# Create new visitor
@router.post("/", response_model=schemas.VisitorResponse, status_code=status.HTTP_201_CREATED)
def create_visitor(
    visitor_data: schemas.VisitorCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # For multi-tenant, ensure village_id matches current user's village
    if visitor_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create visitor for different village"
        )
    
    # Check if property exists and belongs to the same village
    property = db.query(models.Property).filter(
        models.Property.id == visitor_data.property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property not found or belongs to different village"
        )
    
    # For residents, check if they own the property
    if current_user.role == schemas.UserRole.RESIDENT:
        if property.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create visitor for this property"
            )
    
    # Generate entry code if not provided
    if not visitor_data.entry_code:
        visitor_data.entry_code = generate_entry_code()
    
    # Create new visitor
    db_visitor = models.Visitor(**visitor_data.dict())
    
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)
    
    return db_visitor

# Update visitor
@router.put("/{visitor_id}", response_model=schemas.VisitorResponse)
def update_visitor(
    visitor_id: UUID,
    visitor_update: schemas.VisitorUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Check if visitor exists and belongs to the same village
    db_visitor = db.query(models.Visitor).filter(
        models.Visitor.id == visitor_id,
        models.Visitor.village_id == current_user.village_id
    ).first()
    
    if not db_visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )
    
    # For residents, check if they own the property
    if current_user.role == schemas.UserRole.RESIDENT:
        property = db.query(models.Property).filter(
            models.Property.id == db_visitor.property_id,
            models.Property.owner_id == current_user.id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this visitor"
            )
    
    # Update visitor fields
    update_data = visitor_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_visitor, key, value)
    
    db.commit()
    db.refresh(db_visitor)
    
    return db_visitor

# Delete visitor
@router.delete("/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visitor(
    visitor_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Check if visitor exists and belongs to the same village
    db_visitor = db.query(models.Visitor).filter(
        models.Visitor.id == visitor_id,
        models.Visitor.village_id == current_user.village_id
    ).first()
    
    if not db_visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )
    
    # For residents, check if they own the property
    if current_user.role == schemas.UserRole.RESIDENT:
        property = db.query(models.Property).filter(
            models.Property.id == db_visitor.property_id,
            models.Property.owner_id == current_user.id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this visitor"
            )
    
    db.delete(db_visitor)
    db.commit()
    
    return None

# Verify visitor entry code
@router.post("/verify-code", response_model=dict)
def verify_entry_code(
    verification_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only security staff and admin can verify entry codes
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    entry_code = verification_data.get("entry_code")
    if not entry_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entry code is required"
        )
    
    # Find visitor with this entry code
    visitor = db.query(models.Visitor).filter(
        models.Visitor.entry_code == entry_code,
        models.Visitor.village_id == current_user.village_id
    ).first()
    
    if not visitor:
        return {
            "valid": False,
            "message": "Invalid entry code"
        }
    
    # Check if code is expired
    if visitor.valid_until < datetime.now():
        return {
            "valid": False,
            "message": "Entry code has expired",
            "visitor": {
                "id": str(visitor.id),
                "name": visitor.name,
                "property_id": str(visitor.property_id),
                "status": visitor.status
            }
        }
    
    # Check if code has already been used
    if visitor.status == schemas.VisitorStatus.USED:
        return {
            "valid": False,
            "message": "Entry code has already been used",
            "visitor": {
                "id": str(visitor.id),
                "name": visitor.name,
                "property_id": str(visitor.property_id),
                "status": visitor.status
            }
        }
    
    # Update visitor status to USED
    visitor.status = schemas.VisitorStatus.USED
    db.commit()
    
    # Create access log
    access_log = models.AccessLog(
        village_id=current_user.village_id,
        property_id=visitor.property_id,
        timestamp=datetime.now(),
        direction=schemas.AccessDirection.ENTRY,
        access_method="visitor_code",
        status=schemas.AccessStatus.GRANTED
    )
    
    db.add(access_log)
    db.commit()
    
    # Get property details
    property = db.query(models.Property).filter(models.Property.id == visitor.property_id).first()
    
    return {
        "valid": True,
        "message": "Entry code verified successfully",
        "visitor": {
            "id": str(visitor.id),
            "name": visitor.name,
            "property_id": str(visitor.property_id),
            "property_address": property.address if property else None,
            "purpose": visitor.purpose,
            "status": visitor.status
        }
    }

# Helper function to generate random entry code
def generate_entry_code(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))
