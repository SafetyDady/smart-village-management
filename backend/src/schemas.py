from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, time
from enum import Enum
import uuid
from uuid import UUID

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    RESIDENT = "resident"
    VISITOR = "visitor"

class AccessDirection(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"

class AccessStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"

class VisitorStatus(str, Enum):
    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"

class GateOperationMode(str, Enum):
    STAFF_ASSISTED = "staff_assisted"
    AUTOMATED = "automated"

# Base Models
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    village_id: UUID
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PropertyBase(BaseModel):
    village_id: UUID
    address: str
    unit_number: Optional[str] = None
    owner_id: Optional[UUID] = None
    resident_ids: Optional[List[str]] = None
    status: str = "active"

class PropertyCreate(PropertyBase):
    pass

class PropertyUpdate(BaseModel):
    address: Optional[str] = None
    unit_number: Optional[str] = None
    owner_id: Optional[UUID] = None
    resident_ids: Optional[List[str]] = None
    status: Optional[str] = None

class PropertyResponse(PropertyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AccessLogBase(BaseModel):
    village_id: UUID
    property_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    timestamp: datetime
    direction: AccessDirection
    access_method: Optional[str] = None
    status: AccessStatus

class AccessLogCreate(AccessLogBase):
    pass

class AccessLogResponse(AccessLogBase):
    id: UUID

    class Config:
        from_attributes = True

class VisitorBase(BaseModel):
    village_id: UUID
    property_id: UUID
    name: str
    contact: Optional[str] = None
    purpose: Optional[str] = None
    entry_code: Optional[str] = None
    valid_from: datetime
    valid_until: datetime
    status: VisitorStatus = VisitorStatus.PENDING

class VisitorCreate(VisitorBase):
    pass

class VisitorUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    purpose: Optional[str] = None
    entry_code: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: Optional[VisitorStatus] = None

class VisitorResponse(VisitorBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# Gate Schedule Models
class GateScheduleBase(BaseModel):
    village_id: UUID
    gate_id: str
    name: str
    description: Optional[str] = None
    operation_mode: GateOperationMode
    days_of_week: List[int]  # 0=Monday, 6=Sunday
    start_time: time
    end_time: time
    settings: Optional[Dict[str, Any]] = None

class GateScheduleCreate(GateScheduleBase):
    pass

class GateScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    operation_mode: Optional[GateOperationMode] = None
    days_of_week: Optional[List[int]] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    settings: Optional[Dict[str, Any]] = None

class GateScheduleResponse(GateScheduleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True

# Token Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

