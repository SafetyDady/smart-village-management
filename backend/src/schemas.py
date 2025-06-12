from pydantic import BaseModel, Field, EmailStr, UUID4
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums for validation
class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    RESIDENT = "resident"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class PropertyStatus(str, Enum):
    OCCUPIED = "occupied"
    VACANT = "vacant"
    UNDER_MAINTENANCE = "under_maintenance"

class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class AccessDirection(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"

class AccessStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"

class CategoryStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class VisitorStatus(str, Enum):
    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"

# Base schemas
class VillageBase(BaseModel):
    name: str
    address: str
    contact_info: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None

class UserBase(BaseModel):
    village_id: UUID4
    role: UserRole
    username: str
    email: EmailStr
    phone: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE

class PropertyBase(BaseModel):
    village_id: UUID4
    address: str
    owner_id: Optional[UUID4] = None
    resident_ids: Optional[List[UUID4]] = None
    status: PropertyStatus = PropertyStatus.VACANT

class InvoiceBase(BaseModel):
    village_id: UUID4
    property_id: UUID4
    amount: float
    due_date: datetime
    status: InvoiceStatus = InvoiceStatus.PENDING
    items: Optional[List[Dict[str, Any]]] = None

class PaymentBase(BaseModel):
    invoice_id: UUID4
    amount: float
    payment_date: datetime
    payment_method: str
    status: PaymentStatus = PaymentStatus.PENDING
    verification: Optional[Dict[str, Any]] = None
    slip_url: Optional[str] = None

class AccessLogBase(BaseModel):
    village_id: UUID4
    property_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    timestamp: datetime
    direction: AccessDirection
    access_method: str
    status: AccessStatus

class ExpenseBase(BaseModel):
    village_id: UUID4
    category_id: UUID4
    amount: float
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    payment_date: datetime

class ExpenseCategoryBase(BaseModel):
    village_id: UUID4
    name: str
    description: Optional[str] = None
    status: CategoryStatus = CategoryStatus.ACTIVE

class VisitorBase(BaseModel):
    village_id: UUID4
    property_id: UUID4
    name: str
    phone: Optional[str] = None
    purpose: Optional[str] = None
    entry_code: str
    valid_until: datetime
    status: VisitorStatus = VisitorStatus.PENDING

# Create schemas (used for POST requests)
class VillageCreate(VillageBase):
    pass

class UserCreate(UserBase):
    password: str

class PropertyCreate(PropertyBase):
    pass

class InvoiceCreate(InvoiceBase):
    pass

class PaymentCreate(PaymentBase):
    pass

class AccessLogCreate(AccessLogBase):
    pass

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass

class VisitorCreate(VisitorBase):
    pass

# Update schemas (used for PUT/PATCH requests)
class VillageUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact_info: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None

class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[UserStatus] = None
    password: Optional[str] = None

class PropertyUpdate(BaseModel):
    address: Optional[str] = None
    owner_id: Optional[UUID4] = None
    resident_ids: Optional[List[UUID4]] = None
    status: Optional[PropertyStatus] = None

class InvoiceUpdate(BaseModel):
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    status: Optional[InvoiceStatus] = None
    items: Optional[List[Dict[str, Any]]] = None

class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    status: Optional[PaymentStatus] = None
    verification: Optional[Dict[str, Any]] = None
    slip_url: Optional[str] = None

class ExpenseUpdate(BaseModel):
    category_id: Optional[UUID4] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    payment_date: Optional[datetime] = None

class ExpenseCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CategoryStatus] = None

class VisitorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    purpose: Optional[str] = None
    entry_code: Optional[str] = None
    valid_until: Optional[datetime] = None
    status: Optional[VisitorStatus] = None

# Response schemas (used for GET requests)
class VillageResponse(VillageBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserResponse(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class PropertyResponse(PropertyBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class InvoiceResponse(InvoiceBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class PaymentResponse(PaymentBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class AccessLogResponse(AccessLogBase):
    id: UUID4
    created_at: datetime

    class Config:
        orm_mode = True

class ExpenseResponse(ExpenseBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class ExpenseCategoryResponse(ExpenseCategoryBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class VisitorResponse(VisitorBase):
    id: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[UUID4] = None
    village_id: Optional[UUID4] = None
    role: Optional[UserRole] = None
