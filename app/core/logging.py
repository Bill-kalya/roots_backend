import logging
import json
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger
from app.core.config import settings

# Create logs directory if it doesn't exist
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

class EnterpriseJSONFormatter(jsonlogger.JsonFormatter):
    """Structured JSON logging for enterprise"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['service'] = "roots-backend"
        
        # Add request ID if present
        request_id = request_id_var.get()
        if request_id:
            log_record['request_id'] = request_id
        
        # Add trace info for errors
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

def setup_logging():
    """Configure enterprise logging"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    handlers = []
    
    # Console handler with JSON format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(EnterpriseJSONFormatter())
    handlers.append(console_handler)
    
    # File handler for errors (JSON)
    error_handler = logging.FileHandler('logs/error.json')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(EnterpriseJSONFormatter())
    handlers.append(error_handler)
    
    # File handler for audit logs
    audit_handler = logging.FileHandler('logs/audit.json')
    audit_handler.setFormatter(EnterpriseJSONFormatter())
    handlers.append(audit_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL if hasattr(settings, 'LOG_LEVEL') else 'INFO'),
        handlers=handlers
    )

class AuditLogger:
    """Audit logging for compliance"""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
    
    def log_action(
        self,
        user_id: str,
        action: str,
        resource: str,
        resource_id: str,
        details: Dict[str, Any],
        ip_address: str,
        user_agent: str,
        status: str = "success"
    ):
        """Log user action for audit trail"""
        audit_entry = {
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id_var.get()
        }
        self.logger.info(json.dumps(audit_entry))

audit_logger = AuditLogger()