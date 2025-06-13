from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json
import logging

from ..models.notification_models import (
    Notification, NotificationDelivery, NotificationPreference, 
    NotificationTemplate, NotificationType, NotificationPriority,
    NotificationChannel, NotificationStatus
)
from ..models import models
from .. import database

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service class for handling all notification-related operations
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_notification(
        self,
        village_id: str,
        title: str,
        message: str,
        notification_type: NotificationType,
        user_id: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        Create a new notification
        """
        notification = Notification(
            village_id=village_id,
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            data=data or {}
        )
        
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        # Automatically send the notification
        self._send_notification(notification)
        
        return notification
    
    def create_visitor_arrival_notification(
        self,
        village_id: str,
        visitor_name: str,
        resident_user_id: str,
        property_address: str,
        arrival_time: datetime
    ) -> Notification:
        """
        Create a notification for visitor arrival
        """
        title = f"ผู้มาเยือนมาถึงแล้ว"
        message = f"{visitor_name} มาถึงที่ {property_address} เมื่อ {arrival_time.strftime('%H:%M น.')}"
        
        data = {
            "visitor_name": visitor_name,
            "property_address": property_address,
            "arrival_time": arrival_time.isoformat(),
            "event_type": "visitor_arrival"
        }
        
        return self.create_notification(
            village_id=village_id,
            title=title,
            message=message,
            notification_type=NotificationType.VISITOR_ARRIVAL,
            user_id=resident_user_id,
            priority=NotificationPriority.MEDIUM,
            data=data
        )
    
    def create_visitor_departure_notification(
        self,
        village_id: str,
        visitor_name: str,
        resident_user_id: str,
        property_address: str,
        departure_time: datetime
    ) -> Notification:
        """
        Create a notification for visitor departure
        """
        title = f"ผู้มาเยือนออกจากหมู่บ้านแล้ว"
        message = f"{visitor_name} ออกจาก {property_address} เมื่อ {departure_time.strftime('%H:%M น.')}"
        
        data = {
            "visitor_name": visitor_name,
            "property_address": property_address,
            "departure_time": departure_time.isoformat(),
            "event_type": "visitor_departure"
        }
        
        return self.create_notification(
            village_id=village_id,
            title=title,
            message=message,
            notification_type=NotificationType.VISITOR_DEPARTURE,
            user_id=resident_user_id,
            priority=NotificationPriority.LOW,
            data=data
        )
    
    def create_qr_code_used_notification(
        self,
        village_id: str,
        qr_code_type: str,
        user_id: str,
        usage_time: datetime,
        gate_id: str = "main_gate"
    ) -> Notification:
        """
        Create a notification when QR code is used
        """
        if qr_code_type == "visitor":
            title = "QR Code ผู้มาเยือนถูกใช้งาน"
            message = f"QR Code ที่คุณสร้างสำหรับผู้มาเยือนถูกใช้งานเมื่อ {usage_time.strftime('%H:%M น.')}"
        else:
            title = "QR Code ถูกใช้งาน"
            message = f"QR Code ของคุณถูกใช้งานเมื่อ {usage_time.strftime('%H:%M น.')}"
        
        data = {
            "qr_code_type": qr_code_type,
            "usage_time": usage_time.isoformat(),
            "gate_id": gate_id,
            "event_type": "qr_code_used"
        }
        
        return self.create_notification(
            village_id=village_id,
            title=title,
            message=message,
            notification_type=NotificationType.QR_CODE_USED,
            user_id=user_id,
            priority=NotificationPriority.LOW,
            data=data
        )
    
    def create_gate_mode_change_notification(
        self,
        village_id: str,
        gate_id: str,
        new_mode: str,
        change_time: datetime,
        changed_by: Optional[str] = None
    ) -> Notification:
        """
        Create a notification for gate mode changes
        """
        mode_text = "มีเจ้าหน้าที่" if new_mode == "staff_assisted" else "อัตโนมัติ"
        title = f"โหมดการทำงานของไม้กั้นเปลี่ยนแปลง"
        message = f"ไม้กั้น {gate_id} เปลี่ยนเป็นโหมด{mode_text} เมื่อ {change_time.strftime('%H:%M น.')}"
        
        data = {
            "gate_id": gate_id,
            "new_mode": new_mode,
            "change_time": change_time.isoformat(),
            "changed_by": changed_by,
            "event_type": "gate_mode_change"
        }
        
        # Broadcast to all users in the village
        return self.create_notification(
            village_id=village_id,
            title=title,
            message=message,
            notification_type=NotificationType.GATE_MODE_CHANGE,
            user_id=None,  # Broadcast notification
            priority=NotificationPriority.MEDIUM,
            data=data
        )
    
    def create_security_alert_notification(
        self,
        village_id: str,
        alert_type: str,
        alert_message: str,
        alert_time: datetime,
        severity: str = "medium"
    ) -> Notification:
        """
        Create a security alert notification
        """
        priority_map = {
            "low": NotificationPriority.LOW,
            "medium": NotificationPriority.MEDIUM,
            "high": NotificationPriority.HIGH,
            "critical": NotificationPriority.CRITICAL
        }
        
        title = f"แจ้งเตือนความปลอดภัย: {alert_type}"
        message = f"{alert_message} เมื่อ {alert_time.strftime('%H:%M น.')}"
        
        data = {
            "alert_type": alert_type,
            "alert_message": alert_message,
            "alert_time": alert_time.isoformat(),
            "severity": severity,
            "event_type": "security_alert"
        }
        
        # Broadcast to all staff and admin users
        return self.create_notification(
            village_id=village_id,
            title=title,
            message=message,
            notification_type=NotificationType.SECURITY_ALERT,
            user_id=None,  # Broadcast notification
            priority=priority_map.get(severity, NotificationPriority.MEDIUM),
            data=data
        )
    
    def _send_notification(self, notification: Notification):
        """
        Send notification through appropriate channels
        """
        try:
            if notification.user_id:
                # Send to specific user
                self._send_to_user(notification)
            else:
                # Broadcast notification
                self._broadcast_notification(notification)
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {str(e)}")
    
    def _send_to_user(self, notification: Notification):
        """
        Send notification to a specific user based on their preferences
        """
        # Get user preferences
        preferences = self.db.query(NotificationPreference).filter(
            and_(
                NotificationPreference.user_id == notification.user_id,
                NotificationPreference.notification_type == notification.notification_type,
                NotificationPreference.enabled == True
            )
        ).all()
        
        # If no preferences set, use default channels
        if not preferences:
            self._send_via_default_channels(notification)
        else:
            for pref in preferences:
                self._send_via_channel(notification, pref.channel, notification.user_id)
    
    def _broadcast_notification(self, notification: Notification):
        """
        Broadcast notification to all users in the village
        """
        # Get all users in the village
        users = self.db.query(models.User).filter(
            models.User.village_id == notification.village_id
        ).all()
        
        for user in users:
            # Check if user wants to receive this type of notification
            preferences = self.db.query(NotificationPreference).filter(
                and_(
                    NotificationPreference.user_id == user.id,
                    NotificationPreference.notification_type == notification.notification_type,
                    NotificationPreference.enabled == True
                )
            ).all()
            
            if not preferences:
                # Use default channels for broadcast
                self._send_via_channel(notification, NotificationChannel.IN_APP, user.id)
            else:
                for pref in preferences:
                    self._send_via_channel(notification, pref.channel, user.id)
    
    def _send_via_default_channels(self, notification: Notification):
        """
        Send notification via default channels
        """
        # Default channels: in-app and email
        self._send_via_channel(notification, NotificationChannel.IN_APP, notification.user_id)
        self._send_via_channel(notification, NotificationChannel.EMAIL, notification.user_id)
    
    def _send_via_channel(self, notification: Notification, channel: NotificationChannel, user_id: str):
        """
        Send notification via specific channel
        """
        try:
            # Get user information
            user = self.db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                return
            
            # Determine recipient based on channel
            recipient = self._get_recipient_for_channel(user, channel)
            if not recipient:
                return
            
            # Create delivery record
            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel=channel,
                recipient=recipient,
                status=NotificationStatus.PENDING
            )
            
            self.db.add(delivery)
            self.db.commit()
            
            # Send via specific channel
            success = False
            if channel == NotificationChannel.IN_APP:
                success = self._send_in_app(notification, user, delivery)
            elif channel == NotificationChannel.EMAIL:
                success = self._send_email(notification, user, delivery)
            elif channel == NotificationChannel.SMS:
                success = self._send_sms(notification, user, delivery)
            elif channel == NotificationChannel.LINE:
                success = self._send_line(notification, user, delivery)
            elif channel == NotificationChannel.PUSH:
                success = self._send_push(notification, user, delivery)
            
            # Update delivery status
            if success:
                delivery.status = NotificationStatus.SENT
                delivery.delivered_at = datetime.utcnow()
            else:
                delivery.status = NotificationStatus.FAILED
                delivery.failed_at = datetime.utcnow()
                delivery.retry_count += 1
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to send notification via {channel}: {str(e)}")
    
    def _get_recipient_for_channel(self, user: models.User, channel: NotificationChannel) -> Optional[str]:
        """
        Get recipient identifier for the specified channel
        """
        if channel == NotificationChannel.EMAIL:
            return user.email
        elif channel == NotificationChannel.SMS:
            return user.phone_number
        elif channel == NotificationChannel.IN_APP:
            return str(user.id)
        elif channel == NotificationChannel.PUSH:
            return str(user.id)  # Would use device token in real implementation
        elif channel == NotificationChannel.LINE:
            # Would get LINE user ID from user profile
            return None  # Not implemented yet
        
        return None
    
    def _send_in_app(self, notification: Notification, user: models.User, delivery: NotificationDelivery) -> bool:
        """
        Send in-app notification (stored in database for real-time display)
        """
        # In-app notifications are already stored in the database
        # Real-time delivery would be handled by WebSocket connections
        return True
    
    def _send_email(self, notification: Notification, user: models.User, delivery: NotificationDelivery) -> bool:
        """
        Send email notification
        """
        # This would integrate with an email service like SendGrid, AWS SES, etc.
        # For now, we'll simulate success
        logger.info(f"Sending email to {user.email}: {notification.title}")
        return True
    
    def _send_sms(self, notification: Notification, user: models.User, delivery: NotificationDelivery) -> bool:
        """
        Send SMS notification
        """
        # This would integrate with an SMS service like Twilio, AWS SNS, etc.
        # For now, we'll simulate success
        logger.info(f"Sending SMS to {user.phone_number}: {notification.title}")
        return True
    
    def _send_line(self, notification: Notification, user: models.User, delivery: NotificationDelivery) -> bool:
        """
        Send LINE notification
        """
        # This would integrate with LINE Messaging API
        # For now, we'll simulate success
        logger.info(f"Sending LINE message: {notification.title}")
        return True
    
    def _send_push(self, notification: Notification, user: models.User, delivery: NotificationDelivery) -> bool:
        """
        Send push notification
        """
        # This would integrate with Firebase Cloud Messaging or similar
        # For now, we'll simulate success
        logger.info(f"Sending push notification to {user.id}: {notification.title}")
        return True
    
    def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[Notification]:
        """
        Get notifications for a specific user
        """
        query = self.db.query(Notification).filter(
            or_(
                Notification.user_id == user_id,
                Notification.user_id.is_(None)  # Include broadcast notifications
            )
        )
        
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    
    def mark_notification_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark a notification as read for a specific user
        """
        notification = self.db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None)
                )
            )
        ).first()
        
        if notification and not notification.read_at:
            notification.read_at = datetime.utcnow()
            notification.status = NotificationStatus.READ
            self.db.commit()
            return True
        
        return False
    
    def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread notifications for a user
        """
        return self.db.query(Notification).filter(
            and_(
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None)
                ),
                Notification.read_at.is_(None)
            )
        ).count()

def get_notification_service(db: Session = None) -> NotificationService:
    """
    Get notification service instance
    """
    if db is None:
        db = next(database.get_db())
    return NotificationService(db)

