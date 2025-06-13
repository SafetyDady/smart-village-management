from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import enum

from .models import Base

class QRCodeType(enum.Enum):
    VISITOR = "visitor"
    RESIDENT = "resident"
    TEMPORARY = "temporary"

class QRCodeStatus(enum.Enum):
    UNUSED = "unused"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class QRCodeAction(enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"

class QRCodeRecord(Base):
    __tablename__ = "qr_code_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code_hash = Column(String(255), unique=True, nullable=False, index=True)
    
    # Basic information
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=True)
    qr_type = Column(SQLEnum(QRCodeType), nullable=False)
    
    # Visitor information
    visitor_name = Column(String(255), nullable=True)
    visitor_phone = Column(String(20), nullable=True)
    visit_purpose = Column(String(500), nullable=True)
    
    # Creation information
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Validity period
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=False)
    visit_duration_minutes = Column(Integer, default=240)  # 4 hours default
    
    # Usage tracking
    max_entries = Column(Integer, default=1)
    used_entries = Column(Integer, default=0)
    entry_time = Column(DateTime, nullable=True)
    exit_deadline = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    
    # Status
    status = Column(SQLEnum(QRCodeStatus), default=QRCodeStatus.UNUSED)
    is_active = Column(Boolean, default=True)
    
    # Additional data
    notes = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    village = relationship("Village", back_populates="qr_codes")
    property = relationship("Property", back_populates="qr_codes")
    created_by_user = relationship("User", back_populates="created_qr_codes")
    usage_logs = relationship("QRCodeUsageLog", back_populates="qr_code", cascade="all, delete-orphan")
    
    def is_valid_now(self) -> bool:
        """Check if QR code is valid at current time"""
        now = datetime.utcnow()
        return (
            self.is_active and
            self.status in [QRCodeStatus.UNUSED, QRCodeStatus.ACTIVE] and
            self.valid_from <= now <= self.valid_until
        )
    
    def can_enter(self) -> bool:
        """Check if QR code can be used for entry"""
        return (
            self.is_valid_now() and
            self.used_entries < self.max_entries and
            self.status == QRCodeStatus.UNUSED
        )
    
    def can_exit(self) -> bool:
        """Check if QR code can be used for exit"""
        now = datetime.utcnow()
        return (
            self.status == QRCodeStatus.ACTIVE and
            self.entry_time is not None and
            self.exit_deadline is not None and
            now <= self.exit_deadline and
            self.exit_time is None
        )
    
    def mark_entry(self, gate_id: str = None, scanned_by: str = None) -> bool:
        """Mark QR code as used for entry"""
        if not self.can_enter():
            return False
        
        now = datetime.utcnow()
        self.used_entries += 1
        self.entry_time = now
        self.exit_deadline = now + timedelta(minutes=self.visit_duration_minutes)
        self.status = QRCodeStatus.ACTIVE
        
        return True
    
    def mark_exit(self, gate_id: str = None, scanned_by: str = None) -> bool:
        """Mark QR code as used for exit"""
        if not self.can_exit():
            return False
        
        self.exit_time = datetime.utcnow()
        self.status = QRCodeStatus.COMPLETED
        
        return True
    
    def get_remaining_time(self) -> timedelta:
        """Get remaining time for the visit"""
        if self.status != QRCodeStatus.ACTIVE or self.exit_deadline is None:
            return timedelta(0)
        
        now = datetime.utcnow()
        if now >= self.exit_deadline:
            return timedelta(0)
        
        return self.exit_deadline - now

class QRCodeUsageLog(Base):
    __tablename__ = "qr_code_usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code_id = Column(UUID(as_uuid=True), ForeignKey("qr_code_records.id"), nullable=False)
    
    # Action details
    action = Column(SQLEnum(QRCodeAction), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    gate_id = Column(String(100), nullable=True)
    
    # Staff information
    scanned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Additional information
    notes = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Success/failure tracking
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    qr_code = relationship("QRCodeRecord", back_populates="usage_logs")
    scanned_by_user = relationship("User", back_populates="qr_scans")

class QRCodeTemplate(Base):
    __tablename__ = "qr_code_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    
    # Template details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    qr_type = Column(SQLEnum(QRCodeType), nullable=False)
    
    # Default settings
    default_validity_hours = Column(Integer, default=12)
    default_visit_duration_minutes = Column(Integer, default=240)
    default_max_entries = Column(Integer, default=1)
    
    # Template configuration
    settings = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    village = relationship("Village", back_populates="qr_templates")
    created_by_user = relationship("User", back_populates="created_qr_templates")

# Add relationships to existing models
def add_qr_code_relationships():
    """
    This function should be called to add QR code relationships to existing models.
    In a real implementation, these would be added directly to the existing model classes.
    """
    pass

# Example of how to add relationships to existing models:
# Village.qr_codes = relationship("QRCodeRecord", back_populates="village")
# Village.qr_templates = relationship("QRCodeTemplate", back_populates="village")
# Property.qr_codes = relationship("QRCodeRecord", back_populates="property")
# User.created_qr_codes = relationship("QRCodeRecord", back_populates="created_by_user")
# User.qr_scans = relationship("QRCodeUsageLog", back_populates="scanned_by_user")
# User.created_qr_templates = relationship("QRCodeTemplate", back_populates="created_by_user")

