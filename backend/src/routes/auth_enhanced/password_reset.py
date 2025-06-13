from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .. import schemas, database
from ..models import models
from ..utils import auth

router = APIRouter()

# Email configuration (should be moved to environment variables)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USERNAME = "your-email@gmail.com"  # Should be from environment
EMAIL_PASSWORD = "your-app-password"     # Should be from environment
EMAIL_FROM = "Smart Village Management <your-email@gmail.com>"

def generate_reset_token() -> str:
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)

def send_password_reset_email(email: str, token: str, username: str) -> bool:
    """Send password reset email to user"""
    try:
        # Create reset URL (should be configurable)
        reset_url = f"http://localhost:3000/reset-password?token={token}"
        
        # Create email content
        subject = "รีเซ็ตรหัสผ่าน - Smart Village Management"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>รีเซ็ตรหัสผ่าน</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #e74c3c;">รีเซ็ตรหัสผ่าน</h2>
                
                <p>สวัสดี {username},</p>
                
                <p>เราได้รับคำขอให้รีเซ็ตรหัสผ่านสำหรับบัญชีของคุณใน Smart Village Management System</p>
                
                <p>กรุณาคลิกปุ่มด้านล่างเพื่อตั้งรหัสผ่านใหม่:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #e74c3c; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        รีเซ็ตรหัสผ่าน
                    </a>
                </div>
                
                <p>หรือคัดลอกลิงก์นี้ไปวางในเบราว์เซอร์:</p>
                <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 3px;">
                    {reset_url}
                </p>
                
                <p><strong>หมายเหตุ:</strong> ลิงก์นี้จะหมดอายุใน 1 ชั่วโมง</p>
                
                <p><strong>เพื่อความปลอดภัย:</strong></p>
                <ul>
                    <li>หากคุณไม่ได้ขอรีเซ็ตรหัสผ่าน กรุณาเพิกเฉยต่ออีเมลนี้</li>
                    <li>อย่าแชร์ลิงก์นี้กับผู้อื่น</li>
                    <li>ตั้งรหัสผ่านที่แข็งแกร่งและไม่เคยใช้มาก่อน</li>
                </ul>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                <p style="font-size: 12px; color: #666;">
                    อีเมลนี้ส่งจาก Smart Village Management System<br>
                    กรุณาอย่าตอบกลับอีเมลนี้
                </p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        รีเซ็ตรหัสผ่าน - Smart Village Management
        
        สวัสดี {username},
        
        เราได้รับคำขอให้รีเซ็ตรหัสผ่านสำหรับบัญชีของคุณใน Smart Village Management System
        
        กรุณาคลิกลิงก์ด้านล่างเพื่อตั้งรหัสผ่านใหม่:
        {reset_url}
        
        หมายเหตุ: ลิงก์นี้จะหมดอายุใน 1 ชั่วโมง
        
        เพื่อความปลอดภัย:
        - หากคุณไม่ได้ขอรีเซ็ตรหัสผ่าน กรุณาเพิกเฉยต่ออีเมลนี้
        - อย่าแชร์ลิงก์นี้กับผู้อื่น
        - ตั้งรหัสผ่านที่แข็งแกร่งและไม่เคยใช้มาก่อน
        
        --
        Smart Village Management System
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = email
        
        # Add both text and HTML parts
        text_part = MIMEText(text_body, 'plain', 'utf-8')
        html_part = MIMEText(html_body, 'html', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
        return False

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request_data: schemas.PasswordResetRequest,
    db: Session = Depends(database.get_db)
):
    """Request password reset"""
    
    # Find user by email
    user = db.query(models.User).filter(models.User.email == request_data.email).first()
    
    # Always return success message for security (don't reveal if email exists)
    success_message = {"message": "If the email exists in our system, a password reset link has been sent"}
    
    if not user:
        return success_message
    
    # Check if user account is active
    if user.status != models.UserStatus.ACTIVE:
        return success_message
    
    # Delete any existing reset tokens for this user
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id
    ).delete()
    
    # Generate new reset token
    token = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
    
    # Save token to database
    reset_token = models.PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        used=False
    )
    db.add(reset_token)
    db.commit()
    
    # Send reset email
    email_sent = send_password_reset_email(user.email, token, user.username)
    
    if not email_sent:
        # Log error but still return success message for security
        print(f"Failed to send password reset email to {user.email}")
    
    return success_message

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: schemas.PasswordReset,
    db: Session = Depends(database.get_db)
):
    """Reset password using token"""
    
    # Find reset token
    reset_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == reset_data.token,
        models.PasswordResetToken.used == False
    ).first()
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if token has expired
    if datetime.utcnow() > reset_token.expires_at:
        # Delete expired token
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    # Get user
    user = db.query(models.User).filter(
        models.User.id == reset_token.user_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user account is active
    if user.status != models.UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not active"
        )
    
    # Update password
    user.password_hash = auth.get_password_hash(reset_data.new_password)
    
    # Reset login attempts and unlock account
    user.login_attempts = 0
    user.account_locked_until = None
    
    # Mark token as used
    reset_token.used = True
    
    db.commit()
    
    return {"message": "Password reset successfully"}

@router.get("/validate-reset-token/{token}")
async def validate_reset_token(
    token: str,
    db: Session = Depends(database.get_db)
):
    """Validate if reset token is valid and not expired"""
    
    # Find reset token
    reset_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == token,
        models.PasswordResetToken.used == False
    ).first()
    
    if not reset_token:
        return {"valid": False, "message": "Invalid reset token"}
    
    # Check if token has expired
    if datetime.utcnow() > reset_token.expires_at:
        return {"valid": False, "message": "Reset token has expired"}
    
    # Get user to check if account is still active
    user = db.query(models.User).filter(
        models.User.id == reset_token.user_id
    ).first()
    
    if not user or user.status != models.UserStatus.ACTIVE:
        return {"valid": False, "message": "User account is not active"}
    
    return {
        "valid": True, 
        "message": "Token is valid",
        "expires_at": reset_token.expires_at.isoformat()
    }

