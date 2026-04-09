from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    
    # Security fields - Failed login tracking
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime, nullable=True)
    account_locked_until = Column(DateTime, nullable=True)
    lockout_reason = Column(String(255), nullable=True)
    
    # Session management
    last_login = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 ready
    last_login_user_agent = Column(String(500), nullable=True)
    current_session_id = Column(String(255), nullable=True)
    
    # MFA support
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_backup_codes = Column(JSON, nullable=True)  # Store hashed backup codes
    
    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    password_updated_at = Column(DateTime, nullable=True)
    previous_passwords = Column(JSON, nullable=True, default=list)  # Store hashes of last 5 passwords
    
    # Device tracking
    trusted_devices = Column(JSON, nullable=True, default=list)  # Device fingerprints
    
    # Audit fields
    created_by_ip = Column(String(45), nullable=True)
    account_created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Account flags
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    def lock_account(self, reason: str, duration_minutes: int = 30):
        """Lock user account for security reasons"""
        from datetime import timedelta
        self.is_active = False
        self.account_locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.lockout_reason = reason
    
    def unlock_account(self):
        """Unlock user account"""
        self.is_active = True
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.lockout_reason = None
    
    def record_failed_login(self, ip: str = None):
        """Record failed login attempt"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()
        
        # Lock after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.lock_account("Too many failed login attempts", duration_minutes=30)
    
    def record_successful_login(self, ip: str, user_agent: str):
        """Record successful login"""
        self.failed_login_attempts = 0
        self.last_login = datetime.utcnow()
        self.last_login_ip = ip
        self.last_login_user_agent = user_agent
        self.last_activity = datetime.utcnow()
    
    def update_password(self, new_password_hash: str):
        """Update password with history tracking"""
        # Store previous password hash (keep last 5)
        if not self.previous_passwords:
            self.previous_passwords = []
        
        self.previous_passwords.append(self.hashed_password)
        if len(self.previous_passwords) > 5:
            self.previous_passwords.pop(0)
        
        self.hashed_password = new_password_hash
        self.password_updated_at = datetime.utcnow()
        self.password_reset_token = None
        self.password_reset_expires = None
    
    def is_password_reused(self, new_password_hash: str) -> bool:
        """Check if password was used before"""
        return new_password_hash in (self.previous_passwords or [])
    
    def set_password_reset_token(self, token: str, expires_minutes: int = 60):
        """Set password reset token"""
        from datetime import timedelta
        self.password_reset_token = token
        self.password_reset_expires = datetime.utcnow() + timedelta(minutes=expires_minutes)
    
    def verify_reset_token(self, token: str) -> bool:
        """Verify password reset token"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        return (self.password_reset_token == token and 
                datetime.utcnow() < self.password_reset_expires)
    
    def add_trusted_device(self, device_fingerprint: str, device_name: str = None):
        """Add trusted device for MFA skip"""
        if not self.trusted_devices:
            self.trusted_devices = []
        
        device = {
            "fingerprint": device_fingerprint,
            "name": device_name,
            "added_at": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat()
        }
        
        self.trusted_devices.append(device)
        
        # Keep only last 10 devices
        if len(self.trusted_devices) > 10:
            self.trusted_devices = self.trusted_devices[-10:]
    
    def is_device_trusted(self, device_fingerprint: str) -> bool:
        """Check if device is trusted"""
        if not self.trusted_devices:
            return False
        return any(d["fingerprint"] == device_fingerprint for d in self.trusted_devices)