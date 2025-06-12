from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all properties (filtered by village)
@router.get("/", response_model=List[schemas.PropertyResponse])
def get_all_properties(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # For multi-tenant, filter by village_id
    properties = db.query(models.Property).filter(
        models.Property.village_id == current_user.village_id
    ).all()
    
    return properties

# Get property by ID
@router.get("/{property_id}", response_model=schemas.PropertyResponse)
def get_property(
    property_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Check if property exists and belongs to the same village
    property = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return property

# Create new property (admin only)
@router.post("/", response_model=schemas.PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    property_data: schemas.PropertyCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if property_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create property for different village"
        )
    
    # If owner_id is provided, check if user exists and belongs to the same village
    if property_data.owner_id:
        owner = db.query(models.User).filter(
            models.User.id == property_data.owner_id,
            models.User.village_id == current_user.village_id
        ).first()
        
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner not found or belongs to different village"
            )
    
    # Create new property
    db_property = models.Property(**property_data.dict())
    
    db.add(db_property)
    db.commit()
    db.refresh(db_property)
    
    return db_property

# Update property
@router.put("/{property_id}", response_model=schemas.PropertyResponse)
def update_property(
    property_id: UUID,
    property_update: schemas.PropertyUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can update properties
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if property exists and belongs to the same village
    db_property = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not db_property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # If owner_id is provided, check if user exists and belongs to the same village
    if property_update.owner_id:
        owner = db.query(models.User).filter(
            models.User.id == property_update.owner_id,
            models.User.village_id == current_user.village_id
        ).first()
        
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner not found or belongs to different village"
            )
    
    # Update property fields
    update_data = property_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_property, key, value)
    
    db.commit()
    db.refresh(db_property)
    
    return db_property

# Delete property (admin only)
@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if property exists and belongs to the same village
    db_property = db.query(models.Property).filter(
        models.Property.id == property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not db_property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check if property has associated invoices
    invoices = db.query(models.Invoice).filter(
        models.Invoice.property_id == property_id
    ).first()
    
    if invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete property with associated invoices"
        )
    
    db.delete(db_property)
    db.commit()
    
    return None
