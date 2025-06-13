from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

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

def generate_verification_token() -> str:
    """Generate a secure random token for email verification"""
    return secrets.token_urlsafe(32)

def send_verification_email(email: str, token: str, username: str) -> bool:
    """Send verification email to user"""
    try:
        # Create verification URL (should be configurable)
        verification_url = f"http://localhost:3000/verify-email?token={token}"
        
        # Create email content
        subject = "ยืนยันอีเมลของคุณ - Smart Village Management"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>ยืนยันอีเมล</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">ยืนยันอีเมลของคุณ</h2>
                
                <p>สวัสดี {username},</p>
                
                <p>ขอบคุณที่ลงทะเบียนกับ Smart Village Management System</p>
                
                <p>กรุณาคลิกปุ่มด้านล่างเพื่อยืนยันอีเมลของคุณ:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #3498db; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        ยืนยันอีเมล
                    </a>
                </div>
                
                <p>หรือคัดลอกลิงก์นี้ไปวางในเบราว์เซอร์:</p>
                <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 3px;">
                    {verification_url}
                </p>
                
                <p><strong>หมายเหตุ:</strong> ลิงก์นี้จะหมดอายุใน 24 ชั่วโมง</p>
                
                <p>หากคุณไม่ได้ลงทะเบียนบัญชีนี้ กรุณาเพิกเฉยต่ออีเมลนี้</p>
                
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
        ยืนยันอีเมลของคุณ - Smart Village Management
        
        สวัสดี {username},
        
        ขอบคุณที่ลงทะเบียนกับ Smart Village Management System
        
        กรุณาคลิกลิงก์ด้านล่างเพื่อยืนยันอีเมลของคุณ:
        {verification_url}
        
        หมายเหตุ: ลิงก์นี้จะหมดอายุใน 24 ชั่วโมง
        
        หากคุณไม่ได้ลงทะเบียนบัญชีนี้ กรุณาเพิกเฉยต่ออีเมลนี้
        
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
        print(f"Failed to send verification email: {str(e)}")
        return False

@router.post("/send-verification-email", status_code=status.HTTP_200_OK)
async def send_verification_email_endpoint(
    email_data: schemas.EmailVerification,
    db: Session = Depends(database.get_db)
):
    """Send verification email to user"""
    
    # Find user by email
    user = db.query(models.User).filter(models.User.email == email_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if email is already verified
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )
    
    # Delete any existing verification tokens for this user
    db.query(models.EmailVerificationToken).filter(
        models.EmailVerificationToken.user_id == user.id
    ).delete()
    
    # Generate new verification token
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Save token to database
    verification_token = models.EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(verification_token)
    db.commit()
    
    # Send verification email
    email_sent = send_verification_email(user.email, token, user.username)
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )
    
    return {"message": "Verification email sent successfully"}

@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str,
    db: Session = Depends(database.get_db)
):
    """Verify user email using token"""
    
    # Find verification token
    verification_token = db.query(models.EmailVerificationToken).filter(
        models.EmailVerificationToken.token == token
    ).first()
    
    if not verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    # Check if token has expired
    if datetime.utcnow() > verification_token.expires_at:
        # Delete expired token
        db.delete(verification_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired"
        )
    
    # Get user
    user = db.query(models.User).filter(
        models.User.id == verification_token.user_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Mark email as verified
    user.email_verified = True
    
    # Delete verification token
    db.delete(verification_token)
    
    db.commit()
    
    return {"message": "Email verified successfully"}

@router.get("/verification-status/{user_id}")
async def get_verification_status(
    user_id: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Get email verification status for a user"""
    
    # Check if current user can access this information
    if str(current_user.id) != user_id and current_user.role not in [models.UserRole.ADMIN, models.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this information"
        )
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "email": user.email,
        "email_verified": user.email_verified,
        "user_id": str(user.id)
    }

