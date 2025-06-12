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

# Get all expenses (filtered by village)
@router.get("/", response_model=List[schemas.ExpenseResponse])
def get_all_expenses(
    category_id: UUID = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can view expenses
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access expenses"
        )
    
    # Base query
    query = db.query(models.Expense).filter(
        models.Expense.village_id == current_user.village_id
    )
    
    # Filter by category_id if provided
    if category_id:
        query = query.filter(models.Expense.category_id == category_id)
    
    # Order by payment_date descending
    expenses = query.order_by(models.Expense.payment_date.desc()).all()
    
    return expenses

# Get expense by ID
@router.get("/{expense_id}", response_model=schemas.ExpenseResponse)
def get_expense(
    expense_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can view expenses
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access expenses"
        )
    
    # Get the expense
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    # Check if expense belongs to the user's village
    if expense.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this expense"
        )
    
    return expense

# Create new expense (admin and staff only)
@router.post("/", response_model=schemas.ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_data: schemas.ExpenseCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if expense_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create expense for different village"
        )
    
    # Check if category exists and belongs to the same village
    category = db.query(models.ExpenseCategory).filter(
        models.ExpenseCategory.id == expense_data.category_id,
        models.ExpenseCategory.village_id == current_user.village_id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category not found or belongs to different village"
        )
    
    # Create new expense
    db_expense = models.Expense(**expense_data.dict())
    
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    
    return db_expense

# Update expense (admin and staff only)
@router.put("/{expense_id}", response_model=schemas.ExpenseResponse)
def update_expense(
    expense_id: UUID,
    expense_update: schemas.ExpenseUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if expense exists and belongs to the same village
    db_expense = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.village_id == current_user.village_id
    ).first()
    
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    # If category_id is provided, check if it exists and belongs to the same village
    if expense_update.category_id:
        category = db.query(models.ExpenseCategory).filter(
            models.ExpenseCategory.id == expense_update.category_id,
            models.ExpenseCategory.village_id == current_user.village_id
        ).first()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found or belongs to different village"
            )
    
    # Update expense fields
    update_data = expense_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_expense, key, value)
    
    db.commit()
    db.refresh(db_expense)
    
    return db_expense

# Delete expense (admin only)
@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if expense exists and belongs to the same village
    db_expense = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.village_id == current_user.village_id
    ).first()
    
    if not db_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    db.delete(db_expense)
    db.commit()
    
    return None

# Upload expense receipt
@router.post("/{expense_id}/upload-receipt", response_model=schemas.ExpenseResponse)
async def upload_expense_receipt(
    expense_id: UUID,
    receipt: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Get the expense
    expense = db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.village_id == current_user.village_id
    ).first()
    
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found"
        )
    
    # Create directory if it doesn't exist
    upload_dir = f"uploads/expense_receipts/{expense.village_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save the file
    file_extension = os.path.splitext(receipt.filename)[1]
    file_name = f"{expense_id}{file_extension}"
    file_path = f"{upload_dir}/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(receipt.file, buffer)
    
    # Update expense with receipt URL
    expense.receipt_url = file_path
    db.commit()
    db.refresh(expense)
    
    return expense

# Get expense categories
@router.get("/categories/", response_model=List[schemas.ExpenseCategoryResponse])
def get_expense_categories(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Only admin and staff can view expense categories
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access expense categories"
        )
    
    # Get categories for the village
    categories = db.query(models.ExpenseCategory).filter(
        models.ExpenseCategory.village_id == current_user.village_id
    ).all()
    
    return categories

# Create expense category (admin only)
@router.post("/categories/", response_model=schemas.ExpenseCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_expense_category(
    category_data: schemas.ExpenseCategoryCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # For multi-tenant, ensure village_id matches current user's village
    if category_data.village_id != current_user.village_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create category for different village"
        )
    
    # Create new category
    db_category = models.ExpenseCategory(**category_data.dict())
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    return db_category

# Update expense category (admin only)
@router.put("/categories/{category_id}", response_model=schemas.ExpenseCategoryResponse)
def update_expense_category(
    category_id: UUID,
    category_update: schemas.ExpenseCategoryUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if category exists and belongs to the same village
    db_category = db.query(models.ExpenseCategory).filter(
        models.ExpenseCategory.id == category_id,
        models.ExpenseCategory.village_id == current_user.village_id
    ).first()
    
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Update category fields
    update_data = category_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.commit()
    db.refresh(db_category)
    
    return db_category

# Delete expense category (admin only)
@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense_category(
    category_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    
    # Check if category exists and belongs to the same village
    db_category = db.query(models.ExpenseCategory).filter(
        models.ExpenseCategory.id == category_id,
        models.ExpenseCategory.village_id == current_user.village_id
    ).first()
    
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if category has associated expenses
    expenses = db.query(models.Expense).filter(
        models.Expense.category_id == category_id
    ).first()
    
    if expenses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with associated expenses"
        )
    
    db.delete(db_category)
    db.commit()
    
    return None
