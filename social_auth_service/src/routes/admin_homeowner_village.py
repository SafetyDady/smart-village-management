from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, Village, House
from datetime import datetime
import uuid

admin_bp = Blueprint("admin", __name__)
homeowner_bp = Blueprint("homeowner", __name__)
village_house_bp = Blueprint("village_house", __name__)

# Decorator for role-based access control
def require_role(allowed_roles):
    def decorator(f):
        def wrapper(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user or user.role not in allowed_roles:
                return jsonify({"message": "Access denied"}), 403
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# --- Village & House Management ---
@village_house_bp.route("/villages", methods=["GET"])
def get_villages():
    """Get list of all villages"""
    villages = Village.query.all()
    return jsonify({
        "villages": [village.to_dict() for village in villages]
    }), 200

@village_house_bp.route("/villages/<village_id>/houses", methods=["GET"])
def get_houses_in_village(village_id):
    """Get list of houses in a specific village"""
    try:
        village_uuid = uuid.UUID(village_id)
    except ValueError:
        return jsonify({"message": "Invalid village ID"}), 400
    
    village = Village.query.get(village_uuid)
    if not village:
        return jsonify({"message": "Village not found"}), 404
    
    houses = House.query.filter_by(village_id=village_uuid).all()
    return jsonify({
        "village": village.to_dict(),
        "houses": [house.to_dict() for house in houses]
    }), 200

@village_house_bp.route("/villages", methods=["POST"])
@jwt_required()
@require_role(['super_admin'])
def create_village():
    """Create new village (Super Admin only)"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({"message": "Village name is required"}), 400
    
    name = data['name']
    description = data.get('description')
    admin_id = data.get('admin_id')  # Optional: assign admin during creation
    
    # Validate admin if provided
    if admin_id:
        admin_user = User.query.get(admin_id)
        if not admin_user or admin_user.role not in ['admin', 'super_admin']:
            return jsonify({"message": "Invalid admin user"}), 400
    
    new_village = Village(
        name=name,
        description=description,
        admin_id=admin_id
    )
    
    db.session.add(new_village)
    db.session.commit()
    
    return jsonify({
        "message": "Village created successfully",
        "village": new_village.to_dict()
    }), 201

@village_house_bp.route("/houses", methods=["POST"])
@jwt_required()
@require_role(['admin', 'super_admin'])
def create_house():
    """Create new house (Admin only)"""
    data = request.get_json()
    
    required_fields = ['village_id', 'house_number']
    for field in required_fields:
        if not data or field not in data:
            return jsonify({"message": f"{field} is required"}), 400
    
    village_id = data['village_id']
    house_number = data['house_number']
    address = data.get('address')
    
    # Validate village exists
    village = Village.query.get(village_id)
    if not village:
        return jsonify({"message": "Village not found"}), 404
    
    # Check if house number already exists in this village
    existing_house = House.query.filter_by(
        village_id=village_id,
        house_number=house_number
    ).first()
    
    if existing_house:
        return jsonify({"message": "House number already exists in this village"}), 400
    
    new_house = House(
        village_id=village_id,
        house_number=house_number,
        address=address
    )
    
    db.session.add(new_house)
    db.session.commit()
    
    return jsonify({
        "message": "House created successfully",
        "house": new_house.to_dict()
    }), 201

# --- Admin Functions ---
@admin_bp.route("/pending-users", methods=["GET"])
@jwt_required()
@require_role(['admin', 'super_admin'])
def get_pending_users():
    """Get list of users pending admin approval"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # If admin, only show users from their assigned villages
    if current_user.role == 'admin':
        # Find villages where this user is admin
        admin_villages = Village.query.filter_by(admin_id=current_user_id).all()
        village_ids = [v.id for v in admin_villages]
        
        pending_users = User.query.filter(
            User.status == 'pending_admin_approval',
            User.village_id.in_(village_ids)
        ).all()
    else:
        # Super admin can see all pending users
        pending_users = User.query.filter_by(status='pending_admin_approval').all()
    
    return jsonify({
        "pending_users": [user.to_dict() for user in pending_users]
    }), 200

@admin_bp.route("/approve-user/<user_id>", methods=["POST"])
@jwt_required()
@require_role(['admin', 'super_admin'])
def approve_user(user_id):
    """Approve user (Admin/Super Admin)"""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"message": "Invalid user ID"}), 400
    
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_uuid)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    if user.status != 'pending_admin_approval':
        return jsonify({"message": "User is not pending admin approval"}), 400
    
    # Check if admin has permission to approve this user
    if current_user.role == 'admin':
        # Admin can only approve users from their assigned villages
        admin_villages = Village.query.filter_by(admin_id=current_user_id).all()
        village_ids = [v.id for v in admin_villages]
        
        if user.village_id not in village_ids:
            return jsonify({"message": "Access denied: User not in your assigned villages"}), 403
    
    # Approve user
    user.status = 'active'
    user.approved_by_admin = current_user_id
    user.approved_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        "message": "User approved successfully",
        "user": user.to_dict()
    }), 200

@admin_bp.route("/reject-user/<user_id>", methods=["POST"])
@jwt_required()
@require_role(['admin', 'super_admin'])
def reject_user(user_id):
    """Reject user (Admin/Super Admin)"""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"message": "Invalid user ID"}), 400
    
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_uuid)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    data = request.get_json()
    rejection_reason = data.get('reason', 'No reason provided') if data else 'No reason provided'
    
    # Check if admin has permission to reject this user
    if current_user.role == 'admin':
        admin_villages = Village.query.filter_by(admin_id=current_user_id).all()
        village_ids = [v.id for v in admin_villages]
        
        if user.village_id not in village_ids:
            return jsonify({"message": "Access denied: User not in your assigned villages"}), 403
    
    # Reject user
    user.status = 'rejected'
    user.rejected_reason = rejection_reason
    
    db.session.commit()
    
    return jsonify({
        "message": "User rejected successfully",
        "user": user.to_dict()
    }), 200

@admin_bp.route("/assign-admin/<user_id>", methods=["POST"])
@jwt_required()
@require_role(['super_admin'])
def assign_admin(user_id):
    """Assign user as admin (Super Admin only)"""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"message": "Invalid user ID"}), 400
    
    user = User.query.get(user_uuid)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    data = request.get_json()
    village_ids = data.get('village_ids', []) if data else []
    
    # Assign admin role
    user.role = 'admin'
    if user.status != 'active':
        user.status = 'active'
    
    # Assign villages to admin
    if village_ids:
        for village_id in village_ids:
            village = Village.query.get(village_id)
            if village:
                village.admin_id = user.id
    
    db.session.commit()
    
    return jsonify({
        "message": "User assigned as admin successfully",
        "user": user.to_dict(),
        "assigned_villages": village_ids
    }), 200

@admin_bp.route("/users", methods=["GET"])
@jwt_required()
@require_role(['admin', 'super_admin'])
def get_users():
    """Get list of users (Admin/Super Admin)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # If admin, only show users from their assigned villages
    if current_user.role == 'admin':
        admin_villages = Village.query.filter_by(admin_id=current_user_id).all()
        village_ids = [v.id for v in admin_villages]
        
        users = User.query.filter(User.village_id.in_(village_ids)).all()
    else:
        # Super admin can see all users
        users = User.query.all()
    
    return jsonify({
        "users": [user.to_dict() for user in users]
    }), 200

# --- Homeowner Functions ---
@homeowner_bp.route("/pending-members", methods=["GET"])
@jwt_required()
@require_role(['homeowner'])
def get_pending_members():
    """Get list of household members pending homeowner approval"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Find users pending homeowner approval in the same house
    pending_members = User.query.filter(
        User.status == 'pending_homeowner_approval',
        User.village_id == current_user.village_id,
        User.house_number == current_user.house_number,
        User.id != current_user_id
    ).all()
    
    return jsonify({
        "pending_members": [member.to_dict() for member in pending_members]
    }), 200

@homeowner_bp.route("/approve-member/<user_id>", methods=["POST"])
@jwt_required()
@require_role(['homeowner'])
def approve_member(user_id):
    """Approve household member (Homeowner)"""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"message": "Invalid user ID"}), 400
    
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_uuid)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    if user.status != 'pending_homeowner_approval':
        return jsonify({"message": "User is not pending homeowner approval"}), 400
    
    # Check if user is in the same house
    if (user.village_id != current_user.village_id or 
        user.house_number != current_user.house_number):
        return jsonify({"message": "Access denied: User not in your house"}), 403
    
    # Approve member (moves to admin approval)
    user.approved_by_homeowner = current_user_id
    user.status = 'pending_admin_approval'
    
    db.session.commit()
    
    return jsonify({
        "message": "Member approved by homeowner successfully",
        "user": user.to_dict(),
        "next_step": "pending_admin_approval"
    }), 200

@homeowner_bp.route("/reject-member/<user_id>", methods=["POST"])
@jwt_required()
@require_role(['homeowner'])
def reject_member(user_id):
    """Reject household member (Homeowner)"""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"message": "Invalid user ID"}), 400
    
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_uuid)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    data = request.get_json()
    rejection_reason = data.get('reason', 'No reason provided') if data else 'No reason provided'
    
    # Check if user is in the same house
    if (user.village_id != current_user.village_id or 
        user.house_number != current_user.house_number):
        return jsonify({"message": "Access denied: User not in your house"}), 403
    
    # Reject member
    user.status = 'rejected'
    user.rejected_reason = f"Rejected by homeowner: {rejection_reason}"
    
    db.session.commit()
    
    return jsonify({
        "message": "Member rejected by homeowner successfully",
        "user": user.to_dict()
    }), 200

@homeowner_bp.route("/household-members", methods=["GET"])
@jwt_required()
@require_role(['homeowner'])
def get_household_members():
    """Get list of all household members"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Find all users in the same house
    household_members = User.query.filter(
        User.village_id == current_user.village_id,
        User.house_number == current_user.house_number,
        User.id != current_user_id
    ).all()
    
    return jsonify({
        "household_members": [member.to_dict() for member in household_members]
    }), 200

