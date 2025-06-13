from sqlalchemy import Column, String, Integer, Boolean, DateTime, Time, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, time

from ..database import Base

class GateSchedule(Base):
    """
    Model for gate operation schedules
    """
    __tablename__ = "gate_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    gate_id = Column(String, nullable=False, index=True)  # e.g., "main_gate", "secondary_gate"
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Operation mode: "staff_assisted" or "automated"
    operation_mode = Column(String, nullable=False)
    
    # Schedule timing
    days_of_week = Column(ARRAY(Integer), nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Additional settings (JSON)
    settings = Column(JSONB, nullable=True)

class GateOverride(Base):
    """
    Model for temporary gate operation mode overrides
    """
    __tablename__ = "gate_overrides"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    gate_id = Column(String, nullable=False, index=True)
    
    # Operation mode: "staff_assisted" or "automated"
    operation_mode = Column(String, nullable=False)
    
    # When this override expires
    expiry_time = Column(DateTime, nullable=False)
    
    # Who created this override
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

