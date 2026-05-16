from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import json
import uuid
from app.db.base import Base

from typing import Dict, Any, Optional
from fastapi import Request
from app.db.session import get_db
from app.core.logging import audit_logger

class AuditLog(Base):

    """Database audit log table"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_created_at', 'created_at'),
        Index('idx_audit_resource', 'resource', 'resource_id'),
    )

class AuditService:
    """Enterprise audit logging service"""
    
    def __init__(self):
        self.excluded_fields = ['password', 'hashed_password', 'credit_card', 'ssn']
    
    async def log(
        self,
        user_id: Optional[str],
        action: str,
        resource: str,
        resource_id: Optional[str],
        details: Dict[str, Any],
        request: Optional[Request] = None,
        status: str = "success",
        error: Optional[str] = None
    ):
        """Create audit log entry"""
        
        # Sanitize sensitive data
        sanitized_details = self._sanitize_data(details)
        
        # Get request details
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        # Create log entry
        log_entry = {
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "details": sanitized_details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": status,
            "error_message": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log to JSON file (for SIEM)
        # audit_logger.log_action may not accept all keys (e.g., timestamp/error_message)
        pythonlog_entry_for_logger = {k: v for k, v in log_entry.items()
                         if k not in ("timestamp", "error_message")}
        audit_logger.log_action(**pythonlog_entry_for_logger)
        
        # Store in database for querying
        await self._store_in_db(log_entry)
        
        # Check for suspicious activity
        await self._check_suspicious_activity(log_entry)
    
    async def _store_in_db(self, log_entry: Dict):
        """Store audit log in database.

        Audit persistence must never break the primary request flow.
        If the audit table/migration is missing or the DB is unavailable,
        we swallow the exception after logging.
        """
        try:
            async for db in get_db():
                audit_log = AuditLog(
                    user_id=log_entry.get("user_id"),
                    action=log_entry["action"],
                    resource=log_entry["resource"],
                    resource_id=log_entry.get("resource_id"),
                    details=log_entry.get("details"),
                    ip_address=log_entry.get("ip_address"),
                    user_agent=log_entry.get("user_agent"),
                    status=log_entry["status"],
                    error_message=log_entry.get("error_message"),
                )
                db.add(audit_log)
                await db.commit()
                break
        except Exception as e:
            # Use the audit logger/structured logger so failures are observable,
            # but do not re-raise.
            try:
                from app.core.logging import audit_logger

                audit_logger.logger.error(f"Failed to store audit log in DB: {e}")
            except Exception:
                # Fallback: do nothing if even audit_logger isn't available.
                pass

    
    def _sanitize_data(self, data: Dict) -> Dict:
        """Remove sensitive data from logs"""
        if not data:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            if key in self.excluded_fields:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized
    
    async def _check_suspicious_activity(self, log_entry: Dict):
        """Check for suspicious patterns"""
        
        # Multiple failed logins
        if (log_entry["action"] == "login" and 
            log_entry["status"] == "failure"):
            await self._check_brute_force(log_entry)
        
        # Unauthorized access attempts
        if (log_entry["status"] == "failure" and 
            "permission" in (log_entry.get("error_message") or "").lower()):
            await self._alert_unauthorized_access(log_entry)
        
        # Bulk operations
        if "bulk" in log_entry["action"] or "batch" in log_entry["action"]:
            await self._check_bulk_operation(log_entry)
    
    async def _check_brute_force(self, log_entry: Dict):
        """Detect brute force attempts"""
        # Implementation would check recent failures from same IP
        pass
    
    async def _alert_unauthorized_access(self, log_entry: Dict):
        """Alert on unauthorized access attempts"""
        from app.monitoring.alerts import alert_manager, AlertSeverity, AlertType
        
        await alert_manager.send_alert(
            title="Unauthorized Access Attempt",
            message=f"User {log_entry.get('user_id')} attempted unauthorized access to {log_entry['resource']}",
            severity=AlertSeverity.MEDIUM,
            alert_type=AlertType.SECURITY,
            metadata=log_entry
        )
    
    async def _check_bulk_operation(self, log_entry: Dict):
        """Monitor bulk operations"""
        pass

# Global audit service
audit_service = AuditService()

# Decorator for automatic audit logging
def audit_action(action: str, resource: str):
    """Decorator to automatically log actions"""
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from request
            request = kwargs.get('request')
            current_user = kwargs.get('current_user')
            
            user_id = str(current_user.id) if current_user else None
            
            resource_id = kwargs.get('resource_id') or kwargs.get('id')
            
            try:
                result = await func(*args, **kwargs)
                
                await audit_service.log(
                    user_id=user_id,
                    action=action,
                    resource=resource,
                    resource_id=str(resource_id) if resource_id else None,
                    details={"input": kwargs, "output": str(result)},
                    request=request,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                await audit_service.log(
                    user_id=user_id,
                    action=action,
                    resource=resource,
                    resource_id=str(resource_id) if resource_id else None,
                    details={"input": kwargs},
                    request=request,
                    status="failure",
                    error=str(e)
                )
                raise
        
        return wrapper
    return decorator