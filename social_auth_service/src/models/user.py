from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), unique=True, nullable=True) # Not Nullable as per new requirement
    social_id = db.Column(db.String(255), unique=True, nullable=True)
    social_provider = db.Column(Enum('line', 'google', 'facebook', name='social_provider_enum'), nullable=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    line_id = db.Column(db.String(255), nullable=True)
    role = db.Column(Enum('super_admin', 'admin', 'homeowner', 'household_member', name='user_role_enum'), nullable=False, default='household_member')
    status = db.Column(Enum('active', 'pending_details', 'pending_homeowner_approval', 'pending_admin_approval', 'rejected', name='user_status_enum'), nullable=False, default='pending_details')
    village_id = db.Column(UUID(as_uuid=True), ForeignKey('villages.id'), nullable=True)
    house_number = db.Column(db.String(20), nullable=True)
    is_primary_homeowner = db.Column(db.Boolean, default=False)
    approved_by_homeowner = db.Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    approved_by_admin = db.Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<User {self.email or self.social_id}>'

    def to_dict(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'social_id': self.social_id,
            'social_provider': self.social_provider,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'line_id': self.line_id,
            'role': self.role,
            'status': self.status,
            'village_id': str(self.village_id) if self.village_id else None,
            'house_number': self.house_number,
            'is_primary_homeowner': self.is_primary_homeowner,
            'approved_by_homeowner': str(self.approved_by_homeowner) if self.approved_by_homeowner else None,
            'approved_by_admin': str(self.approved_by_admin) if self.approved_by_admin else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'rejected_reason': self.rejected_reason,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }




class Village(db.Model):
    __tablename__ = 'villages'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    admin_id = db.Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Village {self.name}>'

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'admin_id': str(self.admin_id) if self.admin_id else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class House(db.Model):
    __tablename__ = 'houses'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = db.Column(UUID(as_uuid=True), ForeignKey('villages.id'), nullable=False)
    house_number = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=True)
    primary_homeowner_id = db.Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<House {self.house_number} in Village {self.village_id}>'

    def to_dict(self):
        return {
            'id': str(self.id),
            'village_id': str(self.village_id),
            'house_number': self.house_number,
            'address': self.address,
            'primary_homeowner_id': str(self.primary_homeowner_id) if self.primary_homeowner_id else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


