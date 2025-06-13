"""
JWT Token utilities for authentication
"""

from flask_jwt_extended import create_access_token, create_refresh_token
from datetime import timedelta


class JWTHandler:
    """Handler for JWT token operations"""
    
    @staticmethod
    def create_tokens(user_id):
        """
        Create access and refresh tokens for user
        """
        access_token = create_access_token(
            identity=str(user_id),
            expires_delta=timedelta(hours=24)
        )
        
        refresh_token = create_refresh_token(
            identity=str(user_id),
            expires_delta=timedelta(days=30)
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
    
    @staticmethod
    def create_access_token(user_id):
        """
        Create only access token for user
        """
        return create_access_token(
            identity=str(user_id),
            expires_delta=timedelta(hours=24)
        )

