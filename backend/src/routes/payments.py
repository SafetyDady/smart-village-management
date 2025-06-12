from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime
import os
import shutil

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Get all payments (filtered by invoice or user permissions)
@router.get("/", response_model=List[schemas.PaymentResponse])
def get_all_payments(
    invoice_id: UUID = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Base query
    query = db.query(models.Payment)
    
    # Filter by invoice_id if provided
    if invoice_id:
        query = query.filter(models.Payment.invoice_id == invoice_id)
    
    # For admin and staff, return filtered payments
    if current_user.role in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        # Get all invoices for the village
        village_invoices = db.query(models.Invoice).filter(
            models.Invoice.village_id == current_user.village_id
        ).all()
        
        invoice_ids = [invoice.id for invoice in village_invoices]
        
        # Filter payments by these invoice IDs
        payments = query.filter(models.Payment.invoice_id.in_(invoice_ids)).all()
    else:
        # For residents, return only their own payments
        # Get properties owned by the user
        properties = db.query(models.Property).filter(
            models.Property.owner_id == current_user.id,
            models.Property.village_id == current_user.village_id
        ).all()
        
        property_ids = [prop.id for prop in properties]
        
        # Get invoices for these properties
        invoices = db.query(models.Invoice).filter(
            models.Invoice.property_id.in_(property_ids)
        ).all()
        
        invoice_ids = [invoice.id for invoice in invoices]
        
        # Filter payments by these invoice IDs
        payments = query.filter(models.Payment.invoice_id.in_(invoice_ids)).all()
    
    return payments

# Get payment by ID
@router.get("/{payment_id}", response_model=schemas.PaymentResponse)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get the payment
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Get the invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == payment.invoice_id).first()
    
    # Check if invoice belongs to the user's village
    if invoice.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this payment"
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
                detail="Not authorized to access this payment"
            )
    
    return payment

# Create new payment
@router.post("/", response_model=schemas.PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: schemas.PaymentCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Check if invoice exists
    invoice = db.query(models.Invoice).filter(models.Invoice.id == payment_data.invoice_id).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if invoice belongs to the user's village
    if invoice.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create payment for this invoice"
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
                detail="Not authorized to create payment for this invoice"
            )
    
    # Create new payment
    db_payment = models.Payment(**payment_data.dict())
    
    # Set initial status based on user role
    if current_user.role in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        db_payment.status = schemas.PaymentStatus.VERIFIED
    else:
        db_payment.status = schemas.PaymentStatus.PENDING
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    # Update invoice status if payment is verified
    if db_payment.status == schemas.PaymentStatus.VERIFIED:
        update_invoice_status_after_payment(db, invoice, db_payment.amount)
    
    return db_payment

# Upload payment slip
@router.post("/{payment_id}/upload-slip", response_model=schemas.PaymentResponse)
async def upload_payment_slip(
    payment_id: UUID,
    slip: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Get the payment
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Get the invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == payment.invoice_id).first()
    
    # Check if invoice belongs to the user's village
    if invoice.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload slip for this payment"
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
                detail="Not authorized to upload slip for this payment"
            )
    
    # Create directory if it doesn't exist
    upload_dir = f"uploads/payment_slips/{invoice.village_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save the file
    file_extension = os.path.splitext(slip.filename)[1]
    file_name = f"{payment_id}{file_extension}"
    file_path = f"{upload_dir}/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(slip.file, buffer)
    
    # Update payment with slip URL
    payment.slip_url = file_path
    db.commit()
    db.refresh(payment)
    
    return payment

# Verify payment (admin and staff only)
@router.put("/{payment_id}/verify", response_model=schemas.PaymentResponse)
def verify_payment(
    payment_id: UUID,
    verification_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Get the payment
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Get the invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == payment.invoice_id).first()
    
    # Check if invoice belongs to the user's village
    if invoice.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to verify this payment"
        )
    
    # Update payment status
    status_value = verification_data.get("status")
    if status_value not in [schemas.PaymentStatus.VERIFIED, schemas.PaymentStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value"
        )
    
    payment.status = status_value
    payment.verification = {
        "verified_by": str(current_user.id),
        "verified_at": datetime.now().isoformat(),
        "notes": verification_data.get("notes", "")
    }
    
    db.commit()
    db.refresh(payment)
    
    # Update invoice status if payment is verified
    if payment.status == schemas.PaymentStatus.VERIFIED:
        update_invoice_status_after_payment(db, invoice, payment.amount)
    
    return payment

# Helper function to update invoice status after payment
def update_invoice_status_after_payment(db: Session, invoice: models.Invoice, payment_amount: float):
    # Get all verified payments for this invoice
    verified_payments = db.query(models.Payment).filter(
        models.Payment.invoice_id == invoice.id,
        models.Payment.status == schemas.PaymentStatus.VERIFIED
    ).all()
    
    total_paid = sum(payment.amount for payment in verified_payments)
    
    # Update invoice status based on payment amount
    if total_paid >= invoice.amount:
        invoice.status = schemas.InvoiceStatus.PAID
    elif total_paid > 0:
        invoice.status = schemas.InvoiceStatus.PARTIALLY_PAID
    
    db.commit()
