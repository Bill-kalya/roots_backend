from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import hashlib
import json
import pyotp
from jose import jwt

from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.config import settings
from app.security.rate_limiter import RateLimitManager
from app.monitoring.alerts import alert_manager, AlertSeverity, AlertType
from app.security.audit_log import audit_service
import logging

logger = logging.getLogger(__name__)

class MFAService:
    """Multi-factor authentication service"""
    
    @staticmethod
    def generate_secret() -> str:
        return pyotp.random_base32()
    
    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def get_provisioning_uri(secret: str, email: str) -> str:
        return pyotp.totp.TOTP(secret).provisioning_uri(email, issuer_name="Roots")

class SessionManager:
    """Advanced session management"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def create_session(
        self,
        user_id: UUID,
        device_id: str,
        ip_address: str,
        user_agent: str,
        fingerprint: str
    ) -> str:
        """Create new session with device fingerprint"""
        
        session_id = str(UUID(uuid4()))
        session_data = {
            "user_id": str(user_id),
            "device_id": device_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "fingerprint": fingerprint,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "is_active": True
        }
        
        # Store session
        await self.redis.setex(
            f"session:{session_id}",
            7 * 24 * 3600,  # 7 days
            json.dumps(session_data)
        )
        
        # Track user's active sessions
        await self.redis.sadd(f"user_sessions:{user_id}", session_id)
        
        return session_id
    
    async def validate_session(
        self,
        session_id: str,
        fingerprint: str,
        ip_address: str = None
    ) -> Optional[Dict]:
        """Validate session with fingerprint"""
        
        session_data = await self.redis.get(f"session:{session_id}")
        if not session_data:
            return None
        
        session = json.loads(session_data)
        
        # Check fingerprint match
        if session["fingerprint"] != fingerprint:
            await self.invalidate_session(session_id)
            return None
        
        # Check IP if provided (optional)
        if ip_address and session["ip_address"] != ip_address:
            # IP changed - could be suspicious
            await self.flag_suspicious_activity(session_id, "IP changed")
        
        # Update last activity
        session["last_activity"] = datetime.utcnow().isoformat()
        await self.redis.setex(
            f"session:{session_id}",
            7 * 24 * 3600,
            json.dumps(session)
        )
        
        return session
    
    async def invalidate_session(self, session_id: str):
        """Invalidate specific session"""
        session_data = await self.redis.get(f"session:{session_id}")
        if session_data:
            session = json.loads(session_data)
            await self.redis.srem(f"user_sessions:{session['user_id']}", session_id)
            await self.redis.delete(f"session:{session_id}")
    
    async def invalidate_all_user_sessions(self, user_id: UUID):
        """Invalidate all sessions for a user"""
        sessions = await self.redis.smembers(f"user_sessions:{user_id}")
        for session_id in sessions:
            await self.redis.delete(f"session:{session_id}")
        await self.redis.delete(f"user_sessions:{user_id}")
    
    async def flag_suspicious_activity(self, session_id: str, reason: str):
        """Flag suspicious session activity"""
        await alert_manager.send_alert(
            title="Suspicious Session Activity",
            message=f"Session {session_id}: {reason}",
            severity=AlertSeverity.MEDIUM,
            alert_type=AlertType.SECURITY,
            metadata={"session_id": session_id, "reason": reason}
        )

class DeviceFingerprinter:
    """Device fingerprinting for security"""
    
    @staticmethod
    def generate_fingerprint(request) -> str:
        """Generate unique device fingerprint"""
        
        # Collect device data
        device_data = {
            "user_agent": request.headers.get("user-agent", ""),
            "accept_language": request.headers.get("accept-language", ""),
            "accept_encoding": request.headers.get("accept-encoding", ""),
            "sec_ch_ua": request.headers.get("sec-ch-ua", ""),
            "sec_ch_ua_platform": request.headers.get("sec-ch-ua-platform", ""),
            "ip": request.client.host,
        }
        
        # Create hash
        fingerprint_string = json.dumps(device_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

class BruteForceProtector:
    """Protect against brute force attacks"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def record_failed_attempt(self, identifier: str, ip: str) -> Dict:
        """Record failed login attempt"""
        
        key = f"bruteforce:{identifier}:{ip}"
        attempts = await self.redis.incr(key)
        
        if attempts == 1:
            await self.redis.expire(key, 3600)  # 1 hour window
        
        # Determine lockout status
        if attempts >= 10:
            lockout_key = f"lockout:{identifier}:{ip}"
            await self.redis.setex(lockout_key, 1800, "locked")  # 30 min lockout
            return {"is_locked": True, "remaining_attempts": 0, "lockout_seconds": 1800}
        
        return {
            "is_locked": False,
            "remaining_attempts": 10 - attempts,
            "lockout_seconds": 0
        }
    
    async def reset_failed_attempts(self, identifier: str, ip: str):
        """Reset failed attempts on successful login"""
        key = f"bruteforce:{identifier}:{ip}"
        await self.redis.delete(key)
    
    async def is_locked(self, identifier: str, ip: str) -> Tuple[bool, int]:
        """Check if account is locked"""
        lockout_key = f"lockout:{identifier}:{ip}"
        ttl = await self.redis.ttl(lockout_key)
        
        if ttl > 0:
            return True, ttl
        
        return False, 0

class AuthService:
    """Enterprise authentication service with MFA, session management, and brute force protection"""
    
    def __init__(self, db: AsyncSession, redis_client):
        self.db = db
        self.redis = redis_client
        self.session_manager = SessionManager(redis_client)
        self.fingerprinter = DeviceFingerprinter()
        self.brute_force = BruteForceProtector(redis_client)
        self.rate_limiter = RateLimitManager(redis_client)
    
    async def register_user(
        self,
        user_data: UserCreate,
        request = None
    ) -> Optional[UserResponse]:
        """Register new user with validation"""
        
        # Check if user exists
        query = select(User).where(User.email == user_data.email)
        result = await self.db.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError("Email already registered")
        
        # Password already validated by Pydantic schema
        
        # Generate verification token
        import secrets
        from datetime import datetime, timedelta

        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)

        # Create user (inactive until email verified)
        new_user = User(
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            is_active=False,
            is_verified=False,
            is_admin=False,
            verification_token=token,
            verification_token_expires=expires,
            mfa_enabled=False,
            mfa_secret=MFAService.generate_secret() if getattr(user_data, "enable_mfa", False) else None,
            failed_login_attempts=0,
            last_login=None,
            account_locked_until=None
        )

        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        
        # Send verification email
        # IMPORTANT: registration should not fail if provider is misconfigured or blocks SMTP/Resend.
        from app.services.email_service import email_service

        try:
            await email_service.send_verification_email(
                email=new_user.email,
                full_name=new_user.full_name,
                token=token,
            )
        except Exception as e:
            # Avoid crashing the entire request; user can still verify later.
            logger.exception("Email sending failed during registration")
            print(f"Email sending failed: {e}")



        # Audit log
        await audit_service.log(
            user_id=str(new_user.id),

            action="user_register",
            resource="user",
            resource_id=str(new_user.id),
            details={"email": new_user.email},
            request=request,
            status="success"
        )
        
        return UserResponse.model_validate(new_user)
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        request,
        mfa_code: str = None
    ) -> Optional[Dict]:
        """Authenticate user with MFA and brute force protection"""
        
        if request is None:
            raise ValueError("Request context is required for login")
        ip_address = request.client.host
        
        # Check brute force lockout
        is_locked, lockout_seconds = await self.brute_force.is_locked(email, ip_address)
        if is_locked:
            raise ValueError(f"Account temporarily locked. Try again in {lockout_seconds} seconds")
        
        # Get user
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(password, user.hashed_password):
            # Record failed attempt
            lock_status = await self.brute_force.record_failed_attempt(email, ip_address)
            
            await audit_service.log(
                user_id=str(user.id) if user else None,
                action="login_failed",
                resource="auth",
                resource_id=None,
                details={"email": email, "reason": "invalid_credentials"},
                request=request,
                status="failure"
            )
            
            raise ValueError(f"Invalid credentials. {lock_status['remaining_attempts']} attempts remaining")
        
        # Email verification gate
        if not user.is_verified:
            raise ValueError("Please verify your email before logging in")

        # Check if account is locked
        if user.account_locked_until and user.account_locked_until > datetime.utcnow():

            raise ValueError(f"Account locked until {user.account_locked_until}")
        
        # Check MFA if enabled
        if user.mfa_enabled:
            if not mfa_code:
                return {"requires_mfa": True, "user_id": str(user.id)}
            
            if not MFAService.verify_code(user.mfa_secret, mfa_code):
                await audit_service.log(
                    user_id=str(user.id),
                    action="mfa_failed",
                    resource="auth",
                    resource_id=str(user.id),
                    details={},
                    request=request,
                    status="failure"
                )
                raise ValueError("Invalid MFA code")
        
        # Reset brute force counter
        await self.brute_force.reset_failed_attempts(email, ip_address)
        
        # Generate device fingerprint
        fingerprint = self.fingerprinter.generate_fingerprint(request)
        
        # Create session
        session_id = await self.session_manager.create_session(
            user_id=user.id,
            device_id=fingerprint[:32],
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent", ""),
            fingerprint=fingerprint
        )
        
        # Update user last login
        user.last_login = datetime.utcnow()
        user.failed_login_attempts = 0
        await self.db.commit()
        
        # Create tokens
        tokens = await self._create_tokens(user.id, session_id, fingerprint)
        
        # Audit log
        await audit_service.log(
            user_id=str(user.id),
            action="login_success",
            resource="auth",
            resource_id=str(user.id),
            details={"session_id": session_id, "fingerprint": fingerprint},
            request=request,
            status="success"
        )
        
        return {
            "user": UserResponse.model_validate(user),
            "tokens": tokens,
            "session_id": session_id,
            "role": user.role.value,  # Include role in response
            "requires_mfa": False
        }
    
    async def _create_tokens(
        self,
        user_id: UUID,
        session_id: str,
        fingerprint: str
    ) -> Dict[str, str]:
        """Create JWT tokens with binding"""
        
        # Get user to include role in token
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one()
        
        # Create access token with additional claims
        access_token = create_access_token({
            "sub": str(user_id),
            "session_id": session_id,
            "fingerprint": fingerprint,
            "role": user.role.value,  # Include role in token
            "type": "access"
        })
        
        # Create refresh token
        refresh_token = create_refresh_token({
            "sub": str(user_id),
            "session_id": session_id,
            "fingerprint": fingerprint,
            "role": user.role.value,
            "type": "refresh"
        })
        
        # Store refresh token in Redis with binding
        await self.redis.setex(
            f"refresh_token:{user_id}:{session_id}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            json.dumps({
                "token": refresh_token,
                "fingerprint": fingerprint,
                "created_at": datetime.utcnow().isoformat()
            })
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        request,
        current_session_id: str
    ) -> Optional[Dict]:
        """Refresh tokens with validation"""
        
        # Decode refresh token
        from app.core.security import decode_token
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        session_id = payload.get("session_id")
        fingerprint = payload.get("fingerprint")
        
        # Verify session exists and is valid
        session = await self.session_manager.validate_session(
            session_id,
            fingerprint,
            request.client.host
        )
        
        if not session:
            return None
        
        # Verify refresh token in Redis
        stored = await self.redis.get(f"refresh_token:{user_id}:{session_id}")
        if not stored:
            return None
        
        # Generate new tokens
        new_fingerprint = self.fingerprinter.generate_fingerprint(request)
        return await self._create_tokens(UUID(user_id), session_id, new_fingerprint)
    
    async def logout(self, user_id: UUID, session_id: str):
        """Logout user from specific session"""
        
        # Invalidate session
        await self.session_manager.invalidate_session(session_id)
        
        # Remove refresh token
        await self.redis.delete(f"refresh_token:{user_id}:{session_id}")
        
        # Blacklist access token (optional - would need token storage)
        
    async def resend_verification_email(self, user_email: str, request=None) -> bool:
        """Regenerate email verification token and re-send the verification email."""
        query = select(User).where(User.email == user_email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # If already verified, no-op
        if user.is_verified:
            return False

        import secrets
        from datetime import datetime, timedelta

        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)

        user.verification_token = token
        user.verification_token_expires = expires
        # Keep is_active=false until verified
        user.is_active = False
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        from app.services.email_service import email_service

        try:
            await email_service.send_verification_email(
                email=user.email,
                full_name=user.full_name,
                token=token,
            )
        except Exception as e:
            logger.exception("Resend verification email failed")
            print(f"Resend verification email failed: {e}")

        return True

    async def logout_all_devices(self, user_id: UUID):
        """Logout from all devices"""

        
        # Invalidate all sessions
        await self.session_manager.invalidate_all_user_sessions(user_id)
        
        # Remove all refresh tokens for user
        pattern = f"refresh_token:{user_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    async def enable_mfa(self, user_id: UUID) -> Dict:
        """Enable MFA for user"""
        
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        if not user.mfa_secret:
            user.mfa_secret = MFAService.generate_secret()
            await self.db.commit()
        
        provisioning_uri = MFAService.get_provisioning_uri(user.mfa_secret, user.email)
        
        return {
            "secret": user.mfa_secret,
            "provisioning_uri": provisioning_uri,
            "qr_code": await self._generate_qr_code(provisioning_uri)
        }
    
    async def verify_mfa_and_enable(self, user_id: UUID, code: str) -> bool:
        """Verify MFA code and enable MFA"""
        
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not user.mfa_secret:
            return False
        
        if MFAService.verify_code(user.mfa_secret, code):
            user.mfa_enabled = True
            await self.db.commit()
            return True
        
        return False
    
    async def validate_password(self, password: str) -> Dict:
        """Public validation for /api/auth/validate-password endpoint (client-side UX)"""
        from app.schemas.user import PasswordCheckResponse
        from app.core.security import PasswordValidator
        
        is_valid, checks = PasswordValidator.validate(password)
        failed = [k for k, v in checks.items() if not v]
        messages = {
            'min_length': 'at least 8 chars',
            'max_length': '≤128 chars',
            'has_uppercase': 'A-Z',
            'has_lowercase': 'a-z',
            'has_digit': '0-9',
            'has_special': '!@#$ etc',
            'no_common_patterns': 'no repeats/common'
        }
        failed_reqs = [messages.get(k, k.replace('_', ' ').title()) for k in failed]
        
        result = PasswordCheckResponse(
            is_valid=is_valid,
            failed_requirements=failed_reqs,
            checks=checks
        )
        return result.model_dump()
    
    async def _validate_password_strength(self, password: str) -> Dict:
        """Internal compatibility wrapper"""
        return await self.validate_password(password)
    
    async def _generate_qr_code(self, uri: str) -> str:
        """Generate QR code as base64 string"""
        import qrcode
        from io import BytesIO
        import base64
        
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        
        return base64.b64encode(buffered.getvalue()).decode()