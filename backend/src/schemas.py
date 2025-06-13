from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

# Enums
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

class GateOperationMode(str, Enum):
    STAFF_ASSISTED = "staff_assisted"
    AUTOMATED = "automated"

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    phone: Optional[str] = None

class UserCreate(UserBase):
    village_id: uuid.UUID
    role: UserRole
    password: str
    status: UserStatus = UserStatus.ACTIVE

# New schema for user self-registration
class UserRegister(UserBase):
    village_id: uuid.UUID
    password: str
    emergency_contact: Optional[Dict[str, str]] = None
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    password: Optional[str] = None
    email_verified: Optional[bool] = None
    profile_image: Optional[str] = None
    emergency_contact: Optional[Dict[str, str]] = None

class UserResponse(UserBase):
    id: uuid.UUID
    village_id: uuid.UUID
    role: UserRole
    status: UserStatus
    email_verified: Optional[bool] = False
    profile_image: Optional[str] = None
    emergency_contact: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Property schemas
class PropertyBase(BaseModel):
    address: str
    status: PropertyStatus = PropertyStatus.VACANT

class PropertyCreate(PropertyBase):
    village_id: uuid.UUID
    owner_id: Optional[uuid.UUID] = None
    resident_ids: Optional[List[uuid.UUID]] = None

class PropertyUpdate(BaseModel):
    address: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    resident_ids: Optional[List[uuid.UUID]] = None
    status: Optional[PropertyStatus] = None

class PropertyResponse(PropertyBase):
    id: uuid.UUID
    village_id: uuid.UUID
    owner_id: Optional[uuid.UUID] = None
    resident_ids: Optional[List[uuid.UUID]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Invoice schemas
class InvoiceBase(BaseModel):
    amount: float
    due_date: datetime
    status: InvoiceStatus = InvoiceStatus.PENDING
    items: Optional[List[Dict[str, Any]]] = None

class InvoiceCreate(InvoiceBase):
    village_id: uuid.UUID
    property_id: uuid.UUID

class InvoiceUpdate(BaseModel):
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    status: Optional[InvoiceStatus] = None
    items: Optional[List[Dict[str, Any]]] = None

class InvoiceResponse(InvoiceBase):
    id: uuid.UUID
    village_id: uuid.UUID
    property_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Payment schemas
class PaymentBase(BaseModel):
    amount: float
    payment_date: datetime
    payment_method: str
    status: PaymentStatus = PaymentStatus.PENDING
    verification: Optional[Dict[str, Any]] = None
    slip_url: Optional[str] = None

class PaymentCreate(PaymentBase):
    invoice_id: uuid.UUID

class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    status: Optional[PaymentStatus] = None
    verification: Optional[Dict[str, Any]] = None
    slip_url: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: uuid.UUID
    invoice_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Email verification schemas
class EmailVerification(BaseModel):
    email: EmailStr

# Password reset schemas
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

# Password strength check schema
class PasswordStrengthCheck(BaseModel):
    password: str

# Login attempt schema
class LoginAttemptResponse(BaseModel):
    id: str
    user_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    attempted_at: datetime
    failure_reason: Optional[str]

# Security settings response
class SecuritySettingsResponse(BaseModel):
    user_id: str
    email_verified: bool
    two_factor_enabled: bool
    login_attempts: int
    account_locked: bool
    account_locked_until: Optional[datetime]
    last_login: Optional[datetime]
    password_changed_at: Optional[datetime]

