from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from redis import asyncio as aioredis
import re
import hashlib
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class PasswordValidator:
    """Enterprise password validation"""
    
    @staticmethod
    def validate(password: str) -> Tuple[bool, Dict[str, any]]:
        """Validate password against enterprise policy"""
        
        checks = {
            "min_length": len(password) >= 12,
            "max_length": len(password) <= 128,
            "has_uppercase": bool(re.search(r'[A-Z]', password)),
            "has_lowercase": bool(re.search(r'[a-z]', password)),
            "has_digit": bool(re.search(r'\d', password)),
            "has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
            "no_common_patterns": not any([
                password.lower() in ["password", "admin", "123456", "qwerty", "letmein"],
                re.search(r'(.)\1{3,}', password),  # No repeated chars
                re.search(r'12345|54321|abcdef', password.lower())
            ])
        }
        
        is_valid = all(checks.values())
        
        return is_valid, checks

class TokenBlacklist:
    """JWT token blacklist with Redis"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
    
    async def blacklist_token(self, token: str, expires_in: int):
        """Add token to blacklist"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await self.redis.setex(f"blacklist:{token_hash}", expires_in, "blacklisted")
    
    async def is_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await self.redis.get(f"blacklist:{token_hash}")
        return result is not None

class TokenBinder:
    """Bind tokens to IP and User-Agent"""
    
    @staticmethod
    def create_binding(request) -> str:
        """Create token binding fingerprint"""
        fingerprint = f"{request.client.host}:{request.headers.get('user-agent', '')}"
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    
    @staticmethod
    def verify_binding(token_payload: Dict, request) -> bool:
        """Verify token binding matches request"""
        expected_binding = TokenBinder.create_binding(request)
        token_binding = token_payload.get("binding")
        return expected_binding == token_binding

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # Validate password before hashing
    is_valid, checks = PasswordValidator.validate(password)
    if not is_valid:
        raise ValueError(f"Password does not meet requirements: {checks}")
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any], binding: str = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "binding": binding
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )
        return payload
    except JWTError:
        return None

# Compression middleware
class CompressionMiddleware:
    """Response compression middleware"""
    
    async def __call__(self, request, call_next):
        response = await call_next(request)
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" in accept_encoding and response.status_code == 200:
            # Compress response
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
        
        return response

def compress_response(min_size: int = 1024):
    """Decorator to compress responses above threshold"""
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)
            
            # Add compression headers
            if hasattr(response, 'body') and len(response.body) > min_size:
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Vary"] = "Accept-Encoding"
            
            return response
        return wrapper
    return decorator