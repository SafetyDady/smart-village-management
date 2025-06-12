from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all invoices (filtered by village)
@router.get("/", response_model=List[schemas.InvoiceResponse])
def get_all_invoices(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # For admin and staff, return all invoices for the village
    if current_user.role in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        invoices = db.query(models.Invoice).filter(
            models.Invoice.village_id == current_user.village_id
        ).all()
    else:
        # For residents, return only their own invoices
        # Get properties owned by the user
        properties = db.query(models.Property).filter(
            models.Property.owner_id == current_user.id,
            models.Property.village_id == current_user.village_id
        ).all()
        
        property_ids = [prop.id for prop in properties]
        
        invoices = db.query(models.Invoice).filter(
            models.Invoice.property_id.in_(property_ids),
            models.Invoice.village_id == current_user.village_id
        ).all()
    
    return invoices

# Get invoice by ID
@router.get("/{invoice_id}", response_model=schemas.InvoiceResponse)
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Check if invoice exists and belongs to the same village
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.village_id == current_user.village_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # For residents, check if they own the property
    if current_user.role == schemas.UserRole.RESIDENT:
        property = db.query(models.Property).filter(
            models.Property.id == invoice.property_id,
            models.Property.owner_id == current_user.id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this invoice"
            )
    
    return invoice

# Create new invoice (admin and staff only)
@router.post("/", response_model=schemas.InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_data: schemas.InvoiceCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if invoice_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create invoice for different village"
        )
    
    # Check if property exists and belongs to the same village
    property = db.query(models.Property).filter(
        models.Property.id == invoice_data.property_id,
        models.Property.village_id == current_user.village_id
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property not found or belongs to different village"
        )
    
    # Create new invoice
    db_invoice = models.Invoice(**invoice_data.dict())
    
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    
    return db_invoice

# Update invoice (admin and staff only)
@router.put("/{invoice_id}", response_model=schemas.InvoiceResponse)
def update_invoice(
    invoice_id: UUID,
    invoice_update: schemas.InvoiceUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if invoice exists and belongs to the same village
    db_invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.village_id == current_user.village_id
    ).first()
    
    if not db_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if invoice has payments and prevent certain updates
    has_payments = db.query(models.Payment).filter(
        models.Payment.invoice_id == invoice_id
    ).first() is not None
    
    if has_payments and invoice_update.amount is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update amount for invoice with payments"
        )
    
    # Update invoice fields
    update_data = invoice_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_invoice, key, value)
    
    db.commit()
    db.refresh(db_invoice)
    
    return db_invoice

# Delete invoice (admin only)
@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if invoice exists and belongs to the same village
    db_invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.village_id == current_user.village_id
    ).first()
    
    if not db_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if invoice has payments
    payments = db.query(models.Payment).filter(
        models.Payment.invoice_id == invoice_id
    ).first()
    
    if payments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete invoice with associated payments"
        )
    
    db.delete(db_invoice)
    db.commit()
    
    return None

# Generate monthly invoices (admin only)
@router.post("/generate-monthly", response_model=dict)
def generate_monthly_invoices(
    data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Get required parameters
    amount = data.get("amount")
    due_date = data.get("due_date")
    description = data.get("description", "Monthly maintenance fee")
    
    if not amount or not due_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount and due_date are required"
        )
    
    # Convert due_date string to datetime if needed
    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid due_date format"
            )
    
    # Get all properties in the village
    properties = db.query(models.Property).filter(
        models.Property.village_id == current_user.village_id,
        models.Property.status == schemas.PropertyStatus.OCCUPIED
    ).all()
    
    # Create invoices for each property
    created_invoices = []
    for property in properties:
        invoice = models.Invoice(
            village_id=current_user.village_id,
            property_id=property.id,
            amount=amount,
            due_date=due_date,
            status=schemas.InvoiceStatus.PENDING,
            items=[{"description": description, "amount": amount}]
        )
        
        db.add(invoice)
        created_invoices.append(invoice)
    
    db.commit()
    
    return {
        "message": f"Successfully generated {len(created_invoices)} invoices",
        "count": len(created_invoices)
    }
