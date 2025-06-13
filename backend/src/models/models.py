from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum, JSON, Time, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime, time

Base = declarative_base()

class Village(Base):
    __tablename__ = "villages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    contact_info = Column(JSON, nullable=True)
    settings = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="village")
    properties = relationship("Property", back_populates="village")
    invoices = relationship("Invoice", back_populates="village")
    expenses = relationship("Expense", back_populates="village")
    expense_categories = relationship("ExpenseCategory", back_populates="village")
    access_logs = relationship("AccessLog", back_populates="village")
    visitors = relationship("Visitor", back_populates="village")
    gate_schedules = relationship("GateSchedule", back_populates="village")
    gate_overrides = relationship("GateOverride", back_populates="village")

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"
    RESIDENT = "resident"

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    # New fields for enhanced user management
    email_verified = Column(Boolean, default=False)
    profile_image = Column(String(255), nullable=True)
    emergency_contact = Column(JSON, nullable=True)
    login_attempts = Column(Integer, default=0)
    last_login_attempt = Column(DateTime(timezone=True), nullable=True)
    account_locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="users")
    owned_properties = relationship("Property", back_populates="owner")
    access_logs = relationship("AccessLog", back_populates="user")
    created_gate_schedules = relationship("GateSchedule", back_populates="created_by_user")
    created_gate_overrides = relationship("GateOverride", back_populates="created_by_user")

class PropertyStatus(str, enum.Enum):
    OCCUPIED = "occupied"
    VACANT = "vacant"
    UNDER_MAINTENANCE = "under_maintenance"

class Property(Base):
    __tablename__ = "properties"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    address = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resident_ids = Column(JSON, nullable=True)  # Array of User IDs
    status = Column(Enum(PropertyStatus), default=PropertyStatus.VACANT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="properties")
    owner = relationship("User", back_populates="owned_properties")
    invoices = relationship("Invoice", back_populates="property")
    access_logs = relationship("AccessLog", back_populates="property")
    visitors = relationship("Visitor", back_populates="property")

class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)
    items = Column(JSON, nullable=True)  # Invoice line items
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="invoices")
    property = relationship("Property", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    payment_method = Column(String(50), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    verification = Column(JSON, nullable=True)  # Verification details
    slip_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")

class AccessDirection(str, enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"

class AccessStatus(str, enum.Enum):
    GRANTED = "granted"
    DENIED = "denied"

class AccessLog(Base):
    __tablename__ = "access_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    direction = Column(Enum(AccessDirection), nullable=False)
    access_method = Column(String(50), nullable=False)
    status = Column(Enum(AccessStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="access_logs")
    property = relationship("Property", back_populates="access_logs")
    user = relationship("User", back_populates="access_logs")

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("expense_categories.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    receipt_url = Column(String(255), nullable=True)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="expenses")
    category = relationship("ExpenseCategory", back_populates="expenses")

class CategoryStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(CategoryStatus), default=CategoryStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="expense_categories")
    expenses = relationship("Expense", back_populates="category")

class VisitorStatus(str, enum.Enum):
    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"

class Visitor(Base):
    __tablename__ = "visitors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    purpose = Column(Text, nullable=True)
    entry_code = Column(String(20), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(VisitorStatus), default=VisitorStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="visitors")
    property = relationship("Property", back_populates="visitors")

class GateOperationMode(str, enum.Enum):
    STAFF_ASSISTED = "staff_assisted"
    AUTOMATED = "automated"

class GateSchedule(Base):
    """
    Model for gate operation schedules
    """
    __tablename__ = "gate_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False, index=True)
    gate_id = Column(String, nullable=False, index=True)  # e.g., "main_gate", "secondary_gate"
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Operation mode: "staff_assisted" or "automated"
    operation_mode = Column(Enum(GateOperationMode), nullable=False)
    
    # Schedule timing
    days_of_week = Column(ARRAY(Integer), nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Additional settings (JSON)
    settings = Column(JSONB, nullable=True)
    
    # Relationships
    village = relationship("Village", back_populates="gate_schedules")
    created_by_user = relationship("User", back_populates="created_gate_schedules")

class GateOverride(Base):
    """
    Model for temporary gate operation mode overrides
    """
    __tablename__ = "gate_overrides"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False, index=True)
    gate_id = Column(String, nullable=False, index=True)
    
    # Operation mode: "staff_assisted" or "automated"
    operation_mode = Column(Enum(GateOperationMode), nullable=False)
    
    # When this override expires
    expiry_time = Column(DateTime(timezone=True), nullable=False)
    
    # Who created this override
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    village = relationship("Village", back_populates="gate_overrides")
    created_by_user = relationship("User", back_populates="created_gate_overrides")

# New model for email verification tokens
class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User")

# New model for password reset tokens
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User")
