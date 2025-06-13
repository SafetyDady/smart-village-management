from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from .. import database, schemas
from ..models import models
from ..models.notification_models import (
    Notification, NotificationPreference, NotificationType, 
    NotificationChannel, NotificationPriority
)
from ..services.notification_service import get_notification_service, NotificationService
from ..utils import auth

router = APIRouter()

# Get user notifications
@router.get("/", response_model=List[dict])
def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    notification_type: Optional[NotificationType] = Query(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Get notifications for the current user
    """
    notifications = notification_service.get_user_notifications(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
        unread_only=unread_only
    )
    
    # Filter by notification type if specified
    if notification_type:
        notifications = [n for n in notifications if n.notification_type == notification_type]
    
    # Convert to response format
    result = []
    for notification in notifications:
        result.append({
            "id": str(notification.id),
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type.value,
            "priority": notification.priority.value,
            "data": notification.data,
            "status": notification.status.value,
            "created_at": notification.created_at.isoformat(),
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
            "is_read": notification.read_at is not None
        })
    
    return result

# Get unread notification count
@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Get count of unread notifications for the current user
    """
    count = notification_service.get_unread_count(str(current_user.id))
    return {"unread_count": count}

# Mark notification as read
@router.patch("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: UUID,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Mark a notification as read
    """
    success = notification_service.mark_notification_as_read(
        notification_id=str(notification_id),
        user_id=str(current_user.id)
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read"
        )
    
    return {"message": "Notification marked as read"}

# Mark all notifications as read
@router.patch("/mark-all-read")
def mark_all_notifications_as_read(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Mark all notifications as read for the current user
    """
    # Update all unread notifications for the user
    updated_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_at.is_(None)
    ).update({
        "read_at": datetime.utcnow(),
        "status": "read"
    })
    
    # Also update broadcast notifications
    broadcast_updated = db.query(Notification).filter(
        Notification.village_id == current_user.village_id,
        Notification.user_id.is_(None),
        Notification.read_at.is_(None)
    ).update({
        "read_at": datetime.utcnow(),
        "status": "read"
    })
    
    db.commit()
    
    total_updated = updated_count + broadcast_updated
    return {"message": f"Marked {total_updated} notifications as read"}

# Get notification preferences
@router.get("/preferences", response_model=List[dict])
def get_notification_preferences(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get notification preferences for the current user
    """
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).all()
    
    # Convert to response format
    result = []
    for pref in preferences:
        result.append({
            "id": str(pref.id),
            "notification_type": pref.notification_type.value,
            "channel": pref.channel.value,
            "enabled": pref.enabled,
            "settings": pref.settings,
            "created_at": pref.created_at.isoformat(),
            "updated_at": pref.updated_at.isoformat()
        })
    
    return result

# Update notification preferences
@router.put("/preferences")
def update_notification_preferences(
    preferences_data: List[dict],
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Update notification preferences for the current user
    """
    # Delete existing preferences
    db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).delete()
    
    # Create new preferences
    for pref_data in preferences_data:
        try:
            notification_type = NotificationType(pref_data["notification_type"])
            channel = NotificationChannel(pref_data["channel"])
            
            preference = NotificationPreference(
                user_id=current_user.id,
                notification_type=notification_type,
                channel=channel,
                enabled=pref_data.get("enabled", True),
                settings=pref_data.get("settings", {})
            )
            
            db.add(preference)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification type or channel: {str(e)}"
            )
    
    db.commit()
    
    return {"message": "Notification preferences updated successfully"}

# Create test notification (admin only)
@router.post("/test")
def create_test_notification(
    test_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Create a test notification (admin only)
    """
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create test notifications"
        )
    
    title = test_data.get("title", "Test Notification")
    message = test_data.get("message", "This is a test notification")
    notification_type_str = test_data.get("notification_type", "general_announcement")
    priority_str = test_data.get("priority", "medium")
    target_user_id = test_data.get("user_id")  # None for broadcast
    
    try:
        notification_type = NotificationType(notification_type_str)
        priority = NotificationPriority(priority_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification type or priority: {str(e)}"
        )
    
    notification = notification_service.create_notification(
        village_id=str(current_user.village_id),
        title=title,
        message=message,
        notification_type=notification_type,
        user_id=target_user_id,
        priority=priority,
        data={"test": True, "created_by": str(current_user.id)}
    )
    
    return {
        "message": "Test notification created successfully",
        "notification_id": str(notification.id)
    }

# Send visitor arrival notification
@router.post("/visitor-arrival")
def send_visitor_arrival_notification(
    visitor_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Send visitor arrival notification
    """
    # Only staff and admin can send visitor notifications
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send visitor notifications"
        )
    
    visitor_name = visitor_data.get("visitor_name")
    resident_user_id = visitor_data.get("resident_user_id")
    property_address = visitor_data.get("property_address")
    
    if not all([visitor_name, resident_user_id, property_address]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: visitor_name, resident_user_id, property_address"
        )
    
    notification = notification_service.create_visitor_arrival_notification(
        village_id=str(current_user.village_id),
        visitor_name=visitor_name,
        resident_user_id=resident_user_id,
        property_address=property_address,
        arrival_time=datetime.utcnow()
    )
    
    return {
        "message": "Visitor arrival notification sent successfully",
        "notification_id": str(notification.id)
    }

# Send security alert
@router.post("/security-alert")
def send_security_alert(
    alert_data: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Send security alert notification
    """
    # Only staff and admin can send security alerts
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send security alerts"
        )
    
    alert_type = alert_data.get("alert_type", "General Security Alert")
    alert_message = alert_data.get("alert_message")
    severity = alert_data.get("severity", "medium")
    
    if not alert_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert message is required"
        )
    
    notification = notification_service.create_security_alert_notification(
        village_id=str(current_user.village_id),
        alert_type=alert_type,
        alert_message=alert_message,
        alert_time=datetime.utcnow(),
        severity=severity
    )
    
    return {
        "message": "Security alert sent successfully",
        "notification_id": str(notification.id)
    }

