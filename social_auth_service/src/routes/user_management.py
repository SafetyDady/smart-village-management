from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from src.models.user import db, User, Village, House
import uuid

user_bp = Blueprint("user", __name__)

@user_bp.route("/complete-profile", methods=["POST"])
@jwt_required()
def complete_profile():
    """
    Complete user profile after social login
    Expected payload: {
        "first_name": "John",
        "last_name": "Doe", 
        "phone": "0812345678",
        "line_id": "line_user_id",
        "email": "user@example.com", // Optional
        "role_selection": "homeowner|household_member",
        "village_id": "uuid",
        "house_number": "123"
    }
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    if user.status != 'pending_details':
        return jsonify({"message": "Profile already completed"}), 400
    
    # Validate required fields
    required_fields = ['first_name', 'last_name', 'role_selection', 'village_id', 'house_number']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"message": f"{field} is required"}), 400
    
    # Validate village exists
    village = Village.query.get(data['village_id'])
    if not village:
        return jsonify({"message": "Village not found"}), 404
    
    # Update user profile
    user.first_name = data['first_name']
    user.last_name = data['last_name']
    user.phone = data.get('phone')
    user.line_id = data.get('line_id')
    user.village_id = data['village_id']
    user.house_number = data['house_number']
    
    # Update email if provided and not already set
    if data.get('email') and not user.email:
        user.email = data['email']
    
    # Set role and status based on selection
    role_selection = data['role_selection']
    if role_selection == "homeowner":
        user.role = "homeowner"
        user.status = "pending_admin_approval"
        user.is_primary_homeowner = True
        
        # Check if house already exists, if not create it
        house = House.query.filter_by(
            village_id=data['village_id'], 
            house_number=data['house_number']
        ).first()
        
        if not house:
            house = House(
                village_id=data['village_id'],
                house_number=data['house_number'],
                primary_homeowner_id=user.id
            )
            db.session.add(house)
        else:
            # Update primary homeowner if not set
            if not house.primary_homeowner_id:
                house.primary_homeowner_id = user.id
                
    elif role_selection == "household_member":
        user.role = "household_member"
        user.status = "pending_homeowner_approval"
        user.is_primary_homeowner = False
    else:
        return jsonify({"message": "Invalid role selection"}), 400
    
    db.session.commit()
    
    return jsonify({
        "message": "Profile completed successfully", 
        "user": user.to_dict(),
        "next_step": "pending_approval"
    }), 200

@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_user_profile():
    """Get current user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    # Include village and house information
    user_data = user.to_dict()
    if user.village_id:
        village = Village.query.get(user.village_id)
        if village:
            user_data['village'] = village.to_dict()
    
    return jsonify({"user": user_data}), 200

@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_user_profile():
    """Update user profile (limited fields)"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    # Only allow updating certain fields
    updatable_fields = ['first_name', 'last_name', 'phone', 'line_id']
    
    for field in updatable_fields:
        if field in data:
            setattr(user, field, data[field])
    
    # Special handling for email (only if not already set)
    if 'email' in data and not user.email:
        user.email = data['email']
    
    db.session.commit()
    
    return jsonify({
        "message": "Profile updated successfully", 
        "user": user.to_dict()
    }), 200

@user_bp.route("/status", methods=["GET"])
@jwt_required()
def get_user_status():
    """Get current user status and approval information"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    status_info = {
        "status": user.status,
        "role": user.role,
        "approved_by_homeowner": user.approved_by_homeowner,
        "approved_by_admin": user.approved_by_admin,
        "approved_at": user.approved_at.isoformat() if user.approved_at else None,
        "rejected_reason": user.rejected_reason
    }
    
    # Add additional context based on status
    if user.status == 'pending_homeowner_approval':
        # Find homeowner for this house
        house = House.query.filter_by(
            village_id=user.village_id,
            house_number=user.house_number
        ).first()
        
        if house and house.primary_homeowner_id:
            homeowner = User.query.get(house.primary_homeowner_id)
            if homeowner:
                status_info['pending_approval_from'] = {
                    'type': 'homeowner',
                    'name': f"{homeowner.first_name} {homeowner.last_name}",
                    'contact': homeowner.phone
                }
    
    elif user.status == 'pending_admin_approval':
        # Find village admin
        village = Village.query.get(user.village_id)
        if village and village.admin_id:
            admin = User.query.get(village.admin_id)
            if admin:
                status_info['pending_approval_from'] = {
                    'type': 'admin',
                    'name': f"{admin.first_name} {admin.last_name}",
                    'contact': admin.phone
                }
    
    return jsonify(status_info), 200

@user_bp.route("/villages", methods=["GET"])
def get_villages():
    """Get list of available villages"""
    villages = Village.query.all()
    return jsonify({
        "villages": [village.to_dict() for village in villages]
    }), 200

@user_bp.route("/villages/<village_id>/houses", methods=["GET"])
def get_village_houses(village_id):
    """Get list of houses in a village"""
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


