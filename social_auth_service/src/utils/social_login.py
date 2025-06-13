"""
Social Login Integration Utilities
Handles LINE, Google, and Facebook OAuth integration
"""

import os
import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import jwt
from flask import current_app


class SocialLoginHandler:
    """Handler for social login integrations"""
    
    @staticmethod
    def verify_google_token(token):
        """
        Verify Google OAuth token and return user info
        """
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                os.getenv('GOOGLE_CLIENT_ID')
            )
            
            # Extract user information
            user_info = {
                'social_id': idinfo['sub'],
                'social_provider': 'google',
                'email': idinfo.get('email'),
                'first_name': idinfo.get('given_name'),
                'last_name': idinfo.get('family_name'),
                'verified': idinfo.get('email_verified', False)
            }
            
            return user_info
            
        except ValueError as e:
            current_app.logger.error(f"Google token verification failed: {e}")
            return None
    
    @staticmethod
    def verify_line_token(access_token):
        """
        Verify LINE access token and return user info
        """
        try:
            # Verify token with LINE
            verify_url = "https://api.line.me/oauth2/v2.1/verify"
            verify_response = requests.get(
                verify_url,
                params={'access_token': access_token}
            )
            
            if verify_response.status_code != 200:
                return None
            
            # Get user profile
            profile_url = "https://api.line.me/v2/profile"
            headers = {'Authorization': f'Bearer {access_token}'}
            profile_response = requests.get(profile_url, headers=headers)
            
            if profile_response.status_code != 200:
                return None
            
            profile_data = profile_response.json()
            
            user_info = {
                'social_id': profile_data['userId'],
                'social_provider': 'line',
                'first_name': profile_data.get('displayName', '').split(' ')[0] if profile_data.get('displayName') else '',
                'last_name': ' '.join(profile_data.get('displayName', '').split(' ')[1:]) if profile_data.get('displayName') and len(profile_data.get('displayName', '').split(' ')) > 1 else '',
                'line_id': profile_data.get('userId'),
                'verified': True  # LINE tokens are already verified
            }
            
            return user_info
            
        except Exception as e:
            current_app.logger.error(f"LINE token verification failed: {e}")
            return None
    
    @staticmethod
    def verify_facebook_token(access_token):
        """
        Verify Facebook access token and return user info
        """
        try:
            # Verify token with Facebook
            app_token = f"{os.getenv('FACEBOOK_APP_ID')}|{os.getenv('FACEBOOK_APP_SECRET')}"
            verify_url = f"https://graph.facebook.com/debug_token"
            verify_params = {
                'input_token': access_token,
                'access_token': app_token
            }
            
            verify_response = requests.get(verify_url, params=verify_params)
            
            if verify_response.status_code != 200:
                return None
            
            verify_data = verify_response.json()
            
            if not verify_data.get('data', {}).get('is_valid'):
                return None
            
            # Get user profile
            profile_url = "https://graph.facebook.com/me"
            profile_params = {
                'fields': 'id,name,email,first_name,last_name',
                'access_token': access_token
            }
            
            profile_response = requests.get(profile_url, params=profile_params)
            
            if profile_response.status_code != 200:
                return None
            
            profile_data = profile_response.json()
            
            user_info = {
                'social_id': profile_data['id'],
                'social_provider': 'facebook',
                'email': profile_data.get('email'),
                'first_name': profile_data.get('first_name'),
                'last_name': profile_data.get('last_name'),
                'verified': True  # Facebook tokens are already verified
            }
            
            return user_info
            
        except Exception as e:
            current_app.logger.error(f"Facebook token verification failed: {e}")
            return None
    
    @staticmethod
    def get_user_info_from_token(token, provider):
        """
        Get user info from social login token based on provider
        """
        if provider == 'google':
            return SocialLoginHandler.verify_google_token(token)
        elif provider == 'line':
            return SocialLoginHandler.verify_line_token(token)
        elif provider == 'facebook':
            return SocialLoginHandler.verify_facebook_token(token)
        else:
            return None

