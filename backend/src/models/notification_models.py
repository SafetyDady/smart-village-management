from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .models import Base

class NotificationType(enum.Enum):
    ACCESS_CONTROL = "access_control"
    VISITOR_ARRIVAL = "visitor_arrival"
    VISITOR_DEPARTURE = "visitor_departure"
    SECURITY_ALERT = "security_alert"
    GATE_MODE_CHANGE = "gate_mode_change"
    QR_CODE_USED = "qr_code_used"
    SYSTEM_UPDATE = "system_update"
    PAYMENT_REMINDER = "payment_reminder"
    INVOICE_GENERATED = "invoice_generated"
    GENERAL_ANNOUNCEMENT = "general_announcement"

class NotificationPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationChannel(enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    LINE = "line"
    PUSH = "push"

class NotificationStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Null for broadcast notifications
    
    # Notification content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    
    # Metadata
    data = Column(JSON, nullable=True)  # Additional data for the notification
    
    # Status tracking
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    village = relationship("Village", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
    delivery_attempts = relationship("NotificationDelivery", back_populates="notification", cascade="all, delete-orphan")

class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)
    
    # Delivery details
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    recipient = Column(String(255), nullable=False)  # Email, phone number, LINE user ID, etc.
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    
    # Timestamps
    attempted_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    notification = relationship("Notification", back_populates="delivery_attempts")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Preference settings
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    enabled = Column(Boolean, default=True)
    
    # Channel-specific settings
    settings = Column(JSON, nullable=True)  # Channel-specific configuration
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=True)  # Null for system templates
    
    # Template details
    name = Column(String(255), nullable=False)
    notification_type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    
    # Template content
    title_template = Column(String(255), nullable=False)
    message_template = Column(Text, nullable=False)
    
    # Template metadata
    variables = Column(JSON, nullable=True)  # List of variables used in the template
    is_active = Column(Boolean, default=True)
    is_system_template = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    village = relationship("Village", back_populates="notification_templates")

# Add relationships to existing models
def add_notification_relationships():
    """
    This function should be called to add notification relationships to existing models.
    In a real implementation, these would be added directly to the existing model classes.
    """
    pass

# Example of how to add relationships to existing models:
# User.notifications = relationship("Notification", back_populates="user")
# User.notification_preferences = relationship("NotificationPreference", back_populates="user")
# Village.notifications = relationship("Notification", back_populates="village")
# Village.notification_templates = relationship("NotificationTemplate", back_populates="village")

