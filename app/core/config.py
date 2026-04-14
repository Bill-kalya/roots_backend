from typing import List, Optional
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, PostgresDsn, field_validator
from functools import lru_cache
import secrets

class Settings(BaseSettings):
    # Database - Enterprise Configuration
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 30
    DATABASE_MAX_OVERFLOW: int = 60
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_POOL_PRE_PING: bool = True
    DATABASE_ECHO: bool = False
    DATABASE_ECHO_POOL: bool = False
    DATABASE_CONNECT_TIMEOUT: int = 10
    DATABASE_COMMAND_TIMEOUT: int = 60
    
    # Read Replica Support
    DATABASE_REPLICA_URL: Optional[PostgresDsn] = None
    DATABASE_READ_POOL_SIZE: int = 50
    
    # Redis - Enterprise Configuration
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    
    REDIS_CART_TTL: int = 604800  # 7 days
    
    # Redis Cluster Support (for production)
    REDIS_CLUSTER_NODES: Optional[List[str]] = None
    REDIS_CLUSTER: bool = False
    
    # JWT - Enhanced Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Shorter for enterprise
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "roots-api"
    JWT_AUDIENCE: str = "roots-client"
    
    # Security Headers
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("CORS_METHODS", "CORS_HEADERS", mode="before")
    @classmethod
    def parse_cors_lists(cls, v):
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v
    
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_HEADERS: List[str] = ["Authorization", "Content-Type", "Accept"]
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    RATE_LIMIT_BURST: int = 20
    
    # Monitoring
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    
    # Backup & Recovery
    BACKUP_ENABLED: bool = True
    BACKUP_SCHEDULE: str = "0 2 * * *"  # 2 AM daily
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_PATH: str = "/backups/postgres"
    
    # Health Checks
    HEALTH_CHECK_INTERVAL: int = 30
    HEALTH_CHECK_TIMEOUT: int = 5
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use asyncpg driver")
        return v
    
    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith("redis://") and not v.startswith("rediss://"):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

