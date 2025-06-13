from flask import Blueprint, request, jsonify
from src.models.user import db, User
from src.utils.social_login import SocialLoginHandler
from src.utils.jwt_handler import JWTHandler
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/social-login", methods=["POST"])
def social_login():
    """
    Handle social login (LINE, Google, Facebook)
    Expected payload: {
        "token": "access_token_from_frontend",
        "provider": "line|google|facebook"
    }
    """
    data = request.get_json()
    
    if not data or 'token' not in data or 'provider' not in data:
        return jsonify({"message": "Token and provider are required"}), 400
    
    token = data['token']
    provider = data['provider']
    
    if provider not in ['line', 'google', 'facebook']:
        return jsonify({"message": "Invalid provider"}), 400
    
    # Verify token and get user info from social provider
    user_info = SocialLoginHandler.get_user_info_from_token(token, provider)
    
    if not user_info:
        return jsonify({"message": "Invalid token or failed to verify"}), 401
    
    # Check if user exists
    user = User.query.filter_by(
        social_id=user_info['social_id'], 
        social_provider=provider
    ).first()
    
    # Check for super admin
    super_admin_email = os.getenv('SUPER_ADMIN_EMAIL')
    super_admin_google_id = os.getenv('SUPER_ADMIN_GOOGLE_ID')
    super_admin_line_id = os.getenv('SUPER_ADMIN_LINE_ID')
    super_admin_facebook_id = os.getenv('SUPER_ADMIN_FACEBOOK_ID')
    
    is_super_admin = False
    if (user_info.get('email') == super_admin_email or
        (provider == 'google' and user_info['social_id'] == super_admin_google_id) or
        (provider == 'line' and user_info['social_id'] == super_admin_line_id) or
        (provider == 'facebook' and user_info['social_id'] == super_admin_facebook_id)):
        is_super_admin = True
    
    if not user:
        # Create new user
        user = User(
            social_id=user_info['social_id'],
            social_provider=provider,
            email=user_info.get('email'),
            first_name=user_info.get('first_name'),
            last_name=user_info.get('last_name'),
            line_id=user_info.get('line_id'),
            role='super_admin' if is_super_admin else 'household_member',
            status='active' if is_super_admin else 'pending_details'
        )
        db.session.add(user)
        db.session.commit()
    else:
        # Update existing user info if needed
        if user_info.get('email') and not user.email:
            user.email = user_info.get('email')
        if user_info.get('first_name') and not user.first_name:
            user.first_name = user_info.get('first_name')
        if user_info.get('last_name') and not user.last_name:
            user.last_name = user_info.get('last_name')
        if user_info.get('line_id') and not user.line_id:
            user.line_id = user_info.get('line_id')
        
        # Check if user should be promoted to super admin
        if is_super_admin and user.role != 'super_admin':
            user.role = 'super_admin'
            user.status = 'active'
        
        db.session.commit()
    
    # Create JWT tokens
    tokens = JWTHandler.create_tokens(user.id)
    
    # Determine redirect based on user status and role
    if user.status == 'pending_details':
        return jsonify({
            "message": "Please complete your profile", 
            "user": user.to_dict(), 
            "redirect_to": "/complete-profile",
            "tokens": tokens
        }), 200
    elif user.status == 'pending_homeowner_approval' or user.status == 'pending_admin_approval':
        return jsonify({
            "message": "Your account is pending approval", 
            "user": user.to_dict(), 
            "redirect_to": "/approval-status",
            "tokens": tokens
        }), 200
    elif user.status == 'rejected':
        return jsonify({
            "message": "Your account has been rejected", 
            "user": user.to_dict(), 
            "redirect_to": "/rejected-status",
            "tokens": tokens
        }), 200
    else:
        # User is active, proceed to dashboard based on role
        redirect_to = "/dashboard"
        if user.role == 'super_admin':
            redirect_to = "/super-admin-dashboard"
        elif user.role == 'admin':
            redirect_to = "/admin-dashboard"
        elif user.role == 'homeowner':
            redirect_to = "/homeowner-dashboard"
        
        return jsonify({
            "message": "Login successful", 
            "user": user.to_dict(), 
            "redirect_to": redirect_to,
            "tokens": tokens
        }), 200

@auth_bp.route("/email-login", methods=["POST"])
def email_login():
    """
    Handle email/password login
    Expected payload: {
        "email": "user@example.com",
        "password": "password"
    }
    """
    data = request.get_json()
    
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"message": "Email and password are required"}), 400
    
    email = data['email']
    password = data['password']
    
    # Find user by email
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message": "Invalid credentials"}), 401
    
    # TODO: Add password verification here
    # For now, we'll just check if user exists
    
    # Create JWT tokens
    tokens = JWTHandler.create_tokens(user.id)
    
    # Similar logic as social_login for redirection based on status and role
    if user.status == 'pending_details':
        return jsonify({
            "message": "Please complete your profile", 
            "user": user.to_dict(), 
            "redirect_to": "/complete-profile",
            "tokens": tokens
        }), 200
    elif user.status == 'pending_homeowner_approval' or user.status == 'pending_admin_approval':
        return jsonify({
            "message": "Your account is pending approval", 
            "user": user.to_dict(), 
            "redirect_to": "/approval-status",
            "tokens": tokens
        }), 200
    elif user.status == 'rejected':
        return jsonify({
            "message": "Your account has been rejected", 
            "user": user.to_dict(), 
            "redirect_to": "/rejected-status",
            "tokens": tokens
        }), 200
    else:
        redirect_to = "/dashboard"
        if user.role == 'super_admin':
            redirect_to = "/super-admin-dashboard"
        elif user.role == 'admin':
            redirect_to = "/admin-dashboard"
        elif user.role == 'homeowner':
            redirect_to = "/homeowner-dashboard"
        
        return jsonify({
            "message": "Login successful", 
            "user": user.to_dict(), 
            "redirect_to": redirect_to,
            "tokens": tokens
        }), 200

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Handle user logout"""
    # TODO: Add token blacklisting if needed
    return jsonify({"message": "Logged out successfully"}), 200

@auth_bp.route("/refresh-token", methods=["POST"])
def refresh_token():
    """Handle token refresh"""
    # TODO: Implement token refresh logic
    return jsonify({"message": "Token refreshed successfully"}), 200

