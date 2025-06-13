from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from ..models.enhanced_qr_models import (
    QRCodeRecord, QRCodeUsageLog, QRCodeStatus, QRCodeAction, QRCodeType
)
from ..models import models
from ..services.notification_service import NotificationService
from .. import database

logger = logging.getLogger(__name__)

class EnhancedQRCodeService:
    """
    Enhanced QR Code service with advanced time-based validity and manual release capabilities
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
    
    def create_advanced_qr_code(
        self,
        village_id: str,
        created_by: str,
        visitor_name: str,
        qr_type: QRCodeType = QRCodeType.VISITOR,
        property_id: Optional[str] = None,
        visitor_phone: Optional[str] = None,
        visit_purpose: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        visit_duration_minutes: int = 240,
        max_entries: int = 1,
        notes: Optional[str] = None
    ) -> QRCodeRecord:
        """
        Create an advanced QR code with configurable validity and visit duration
        """
        now = datetime.utcnow()
        
        # Set default validity period if not provided
        if valid_from is None:
            valid_from = now
        if valid_until is None:
            valid_until = valid_from + timedelta(hours=12)  # Default 12 hours validity
        
        # Generate unique QR code hash
        import hashlib
        import secrets
        
        qr_data = f"{village_id}:{visitor_name}:{valid_from.isoformat()}:{secrets.token_hex(16)}"
        qr_code_hash = hashlib.sha256(qr_data.encode()).hexdigest()
        
        # Create QR code record
        qr_record = QRCodeRecord(
            qr_code_hash=qr_code_hash,
            village_id=village_id,
            property_id=property_id,
            qr_type=qr_type,
            visitor_name=visitor_name,
            visitor_phone=visitor_phone,
            visit_purpose=visit_purpose,
            created_by=created_by,
            valid_from=valid_from,
            valid_until=valid_until,
            visit_duration_minutes=visit_duration_minutes,
            max_entries=max_entries,
            notes=notes
        )
        
        self.db.add(qr_record)
        self.db.commit()
        self.db.refresh(qr_record)
        
        return qr_record
    
    def verify_and_use_qr_code(
        self,
        qr_code_hash: str,
        action: QRCodeAction,
        gate_id: str = "main_gate",
        scanned_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify and use QR code for entry or exit
        """
        # Find QR code record
        qr_record = self.db.query(QRCodeRecord).filter(
            QRCodeRecord.qr_code_hash == qr_code_hash
        ).first()
        
        if not qr_record:
            return {
                "success": False,
                "error": "QR code not found",
                "error_code": "QR_NOT_FOUND"
            }
        
        # Log the attempt
        usage_log = QRCodeUsageLog(
            qr_code_id=qr_record.id,
            action=action,
            gate_id=gate_id,
            scanned_by=scanned_by,
            notes=notes,
            success=False  # Will be updated if successful
        )
        
        try:
            if action == QRCodeAction.ENTRY:
                result = self._handle_entry(qr_record, gate_id, scanned_by)
            elif action == QRCodeAction.EXIT:
                result = self._handle_exit(qr_record, gate_id, scanned_by)
            else:
                result = {
                    "success": False,
                    "error": "Invalid action",
                    "error_code": "INVALID_ACTION"
                }
            
            # Update usage log
            usage_log.success = result["success"]
            if not result["success"]:
                usage_log.error_message = result.get("error", "Unknown error")
            
            self.db.add(usage_log)
            self.db.commit()
            
            # Send notifications if successful
            if result["success"]:
                self._send_usage_notification(qr_record, action, gate_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing QR code {qr_code_hash}: {str(e)}")
            usage_log.error_message = str(e)
            self.db.add(usage_log)
            self.db.commit()
            
            return {
                "success": False,
                "error": "Internal error occurred",
                "error_code": "INTERNAL_ERROR"
            }
    
    def _handle_entry(self, qr_record: QRCodeRecord, gate_id: str, scanned_by: Optional[str]) -> Dict[str, Any]:
        """Handle QR code entry"""
        if not qr_record.can_enter():
            if not qr_record.is_valid_now():
                if datetime.utcnow() < qr_record.valid_from:
                    return {
                        "success": False,
                        "error": f"QR code is not yet valid. Valid from: {qr_record.valid_from.strftime('%Y-%m-%d %H:%M')}",
                        "error_code": "NOT_YET_VALID"
                    }
                else:
                    return {
                        "success": False,
                        "error": "QR code has expired",
                        "error_code": "EXPIRED"
                    }
            elif qr_record.used_entries >= qr_record.max_entries:
                return {
                    "success": False,
                    "error": "QR code has already been used for maximum entries",
                    "error_code": "MAX_ENTRIES_REACHED"
                }
            elif qr_record.status != QRCodeStatus.UNUSED:
                return {
                    "success": False,
                    "error": f"QR code status is {qr_record.status.value}",
                    "error_code": "INVALID_STATUS"
                }
        
        # Mark entry
        success = qr_record.mark_entry(gate_id, scanned_by)
        if success:
            self.db.commit()
            
            # Schedule automatic release notification
            self._schedule_release_notification(qr_record)
            
            return {
                "success": True,
                "message": "Entry successful",
                "visitor_name": qr_record.visitor_name,
                "entry_time": qr_record.entry_time.isoformat(),
                "exit_deadline": qr_record.exit_deadline.isoformat(),
                "remaining_time_minutes": int(qr_record.get_remaining_time().total_seconds() / 60)
            }
        else:
            return {
                "success": False,
                "error": "Failed to mark entry",
                "error_code": "ENTRY_FAILED"
            }
    
    def _handle_exit(self, qr_record: QRCodeRecord, gate_id: str, scanned_by: Optional[str]) -> Dict[str, Any]:
        """Handle QR code exit"""
        if not qr_record.can_exit():
            if qr_record.status != QRCodeStatus.ACTIVE:
                return {
                    "success": False,
                    "error": f"QR code is not active for exit. Status: {qr_record.status.value}",
                    "error_code": "NOT_ACTIVE"
                }
            elif qr_record.entry_time is None:
                return {
                    "success": False,
                    "error": "No entry record found",
                    "error_code": "NO_ENTRY_RECORD"
                }
            elif qr_record.exit_time is not None:
                return {
                    "success": False,
                    "error": "Already exited",
                    "error_code": "ALREADY_EXITED"
                }
            elif datetime.utcnow() > qr_record.exit_deadline:
                return {
                    "success": False,
                    "error": "Exit deadline has passed. Please contact security or use manual release.",
                    "error_code": "EXIT_DEADLINE_PASSED"
                }
        
        # Mark exit
        success = qr_record.mark_exit(gate_id, scanned_by)
        if success:
            self.db.commit()
            return {
                "success": True,
                "message": "Exit successful",
                "visitor_name": qr_record.visitor_name,
                "entry_time": qr_record.entry_time.isoformat(),
                "exit_time": qr_record.exit_time.isoformat(),
                "visit_duration_minutes": int((qr_record.exit_time - qr_record.entry_time).total_seconds() / 60)
            }
        else:
            return {
                "success": False,
                "error": "Failed to mark exit",
                "error_code": "EXIT_FAILED"
            }
    
    def manual_release_qr_code(
        self,
        qr_code_id: str,
        released_by: str,
        reason: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Manually release a QR code (mark as exited) by the property owner or admin
        """
        qr_record = self.db.query(QRCodeRecord).filter(
            QRCodeRecord.id == qr_code_id
        ).first()
        
        if not qr_record:
            return {
                "success": False,
                "error": "QR code not found",
                "error_code": "QR_NOT_FOUND"
            }
        
        # Check if user has permission to release this QR code
        user = self.db.query(models.User).filter(models.User.id == released_by).first()
        if not user:
            return {
                "success": False,
                "error": "User not found",
                "error_code": "USER_NOT_FOUND"
            }
        
        # Check permissions
        can_release = (
            user.role in [models.UserRole.ADMIN, models.UserRole.STAFF] or  # Admin/Staff can release any
            str(qr_record.created_by) == released_by or  # Creator can release their own
            (qr_record.property_id and self._user_owns_property(user.id, qr_record.property_id))  # Property owner can release
        )
        
        if not can_release:
            return {
                "success": False,
                "error": "Not authorized to release this QR code",
                "error_code": "NOT_AUTHORIZED"
            }
        
        # Check if QR code can be released
        if qr_record.status != QRCodeStatus.ACTIVE:
            return {
                "success": False,
                "error": f"QR code cannot be released. Current status: {qr_record.status.value}",
                "error_code": "CANNOT_RELEASE"
            }
        
        # Perform manual release
        qr_record.exit_time = datetime.utcnow()
        qr_record.status = QRCodeStatus.COMPLETED
        
        # Log the manual release
        release_log = QRCodeUsageLog(
            qr_code_id=qr_record.id,
            action=QRCodeAction.EXIT,
            gate_id="manual_release",
            scanned_by=released_by,
            notes=f"Manual release: {reason}. {notes or ''}",
            success=True,
            metadata={"release_reason": reason, "manual_release": True}
        )
        
        self.db.add(release_log)
        self.db.commit()
        
        # Send notification about manual release
        self._send_manual_release_notification(qr_record, user, reason)
        
        return {
            "success": True,
            "message": "QR code manually released",
            "visitor_name": qr_record.visitor_name,
            "released_by": user.full_name,
            "release_time": qr_record.exit_time.isoformat(),
            "reason": reason
        }
    
    def get_active_qr_codes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active QR codes created by a user that need manual release
        """
        # Get QR codes that are active and past their exit deadline
        now = datetime.utcnow()
        
        active_qr_codes = self.db.query(QRCodeRecord).filter(
            and_(
                QRCodeRecord.created_by == user_id,
                QRCodeRecord.status == QRCodeStatus.ACTIVE,
                QRCodeRecord.exit_deadline < now
            )
        ).all()
        
        result = []
        for qr_record in active_qr_codes:
            overdue_minutes = int((now - qr_record.exit_deadline).total_seconds() / 60)
            result.append({
                "id": str(qr_record.id),
                "visitor_name": qr_record.visitor_name,
                "entry_time": qr_record.entry_time.isoformat(),
                "exit_deadline": qr_record.exit_deadline.isoformat(),
                "overdue_minutes": overdue_minutes,
                "visit_purpose": qr_record.visit_purpose,
                "property_address": qr_record.property.address if qr_record.property else None
            })
        
        return result
    
    def _schedule_release_notification(self, qr_record: QRCodeRecord):
        """
        Schedule notifications to remind about manual release
        """
        # This would typically be handled by a background job scheduler
        # For now, we'll create a notification that will be sent when the deadline passes
        pass
    
    def _send_usage_notification(self, qr_record: QRCodeRecord, action: QRCodeAction, gate_id: str):
        """
        Send notification about QR code usage
        """
        if action == QRCodeAction.ENTRY:
            self.notification_service.create_visitor_arrival_notification(
                village_id=str(qr_record.village_id),
                visitor_name=qr_record.visitor_name,
                resident_user_id=str(qr_record.created_by),
                property_address=qr_record.property.address if qr_record.property else "Unknown",
                arrival_time=qr_record.entry_time
            )
        elif action == QRCodeAction.EXIT:
            self.notification_service.create_visitor_departure_notification(
                village_id=str(qr_record.village_id),
                visitor_name=qr_record.visitor_name,
                resident_user_id=str(qr_record.created_by),
                property_address=qr_record.property.address if qr_record.property else "Unknown",
                departure_time=qr_record.exit_time
            )
    
    def _send_manual_release_notification(self, qr_record: QRCodeRecord, released_by_user: models.User, reason: str):
        """
        Send notification about manual QR code release
        """
        title = "QR Code ถูก Release แบบ Manual"
        message = f"QR Code ของ {qr_record.visitor_name} ถูก Release โดย {released_by_user.full_name} เหตุผล: {reason}"
        
        self.notification_service.create_notification(
            village_id=str(qr_record.village_id),
            title=title,
            message=message,
            notification_type=self.notification_service.NotificationType.QR_CODE_USED,
            user_id=str(qr_record.created_by),
            data={
                "qr_code_id": str(qr_record.id),
                "visitor_name": qr_record.visitor_name,
                "released_by": released_by_user.full_name,
                "release_reason": reason,
                "manual_release": True
            }
        )
    
    def _user_owns_property(self, user_id: str, property_id: str) -> bool:
        """
        Check if user owns the specified property
        """
        property_record = self.db.query(models.Property).filter(
            and_(
                models.Property.id == property_id,
                models.Property.owner_id == user_id
            )
        ).first()
        
        return property_record is not None
    
    def send_overdue_release_notifications(self):
        """
        Send notifications for QR codes that are overdue for release
        This should be called by a background job periodically
        """
        now = datetime.utcnow()
        
        # Find QR codes that are active and past their exit deadline
        overdue_qr_codes = self.db.query(QRCodeRecord).filter(
            and_(
                QRCodeRecord.status == QRCodeStatus.ACTIVE,
                QRCodeRecord.exit_deadline < now - timedelta(minutes=15)  # 15 minutes grace period
            )
        ).all()
        
        for qr_record in overdue_qr_codes:
            overdue_minutes = int((now - qr_record.exit_deadline).total_seconds() / 60)
            
            title = "QR Code ต้องการ Manual Release"
            message = f"QR Code ของ {qr_record.visitor_name} เกินเวลาออกแล้ว {overdue_minutes} นาที กรุณา Release แบบ Manual"
            
            self.notification_service.create_notification(
                village_id=str(qr_record.village_id),
                title=title,
                message=message,
                notification_type=self.notification_service.NotificationType.QR_CODE_USED,
                user_id=str(qr_record.created_by),
                priority=self.notification_service.NotificationPriority.HIGH,
                data={
                    "qr_code_id": str(qr_record.id),
                    "visitor_name": qr_record.visitor_name,
                    "overdue_minutes": overdue_minutes,
                    "requires_manual_release": True
                }
            )

def get_enhanced_qr_service(db: Session = None) -> EnhancedQRCodeService:
    """
    Get enhanced QR code service instance
    """
    if db is None:
        db = next(database.get_db())
    return EnhancedQRCodeService(db)

