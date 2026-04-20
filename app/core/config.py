from typing import List, Optional
from pydantic import ConfigDict, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets
import json


class Settings(BaseSettings):

    # =========================================================================
    # APPLICATION
    # =========================================================================
    APP_NAME: str = "Roots API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # =========================================================================
    # DATABASE — Enterprise Configuration
    # =========================================================================
    DATABASE_URL: str
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
    DATABASE_REPLICA_URL: Optional[str] = None
    DATABASE_READ_POOL_SIZE: int = 50

    @field_validator("DATABASE_URL", "DATABASE_REPLICA_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"DATABASE_URL must use asyncpg driver "
                f"(postgresql+asyncpg://...). Got: {v[:30]}..."
            )
        return v

    # =========================================================================
    # REDIS — Enterprise Configuration
    # =========================================================================
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_HEALTH_CHECK_INTERVAL: int = 30

    # Cart TTL — fixes AttributeError in CartService
    REDIS_CART_TTL: int = 604800        # 7 days in seconds
    REDIS_SESSION_TTL: int = 86400      # 24 hours
    REDIS_CACHE_TTL: int = 3600         # 1 hour (general cache)
    REDIS_RATE_LIMIT_TTL: int = 60      # matches RATE_LIMIT_PERIOD

    # Redis Cluster Support
    REDIS_CLUSTER_NODES: Optional[List[str]] = None
    REDIS_CLUSTER: bool = False

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith("redis://") and not v.startswith("rediss://"):
            raise ValueError(
                "REDIS_URL must start with redis:// or rediss://"
            )
        return v

    @field_validator("REDIS_CLUSTER_NODES", mode="before")
    @classmethod
    def parse_redis_cluster_nodes(cls, v) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [n.strip() for n in v.split(",") if n.strip()]
        return v

    # =========================================================================
    # JWT — Enhanced Security
    # =========================================================================
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "roots-api"
    JWT_AUDIENCE: str = "roots-client"

    # =========================================================================
    # CORS — Fixed: safe defaults + robust parser
    # =========================================================================
    # Explicit dev origins so the list is never empty in development.
    # Override in .env with:
    #   CORS_ORIGINS=["https://yourapp.com","https://www.yourapp.com"]
    # or comma-separated:
    #   CORS_ORIGINS=https://yourapp.com,https://www.yourapp.com
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",    # Vite default
        "http://localhost:3000",    # CRA / Next.js default
        "http://localhost:4173",    # Vite preview
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_HEADERS: List[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",     # used by your request_id middleware
        "X-Refresh-Token",
    ]
    CORS_MAX_AGE: int = 600  # seconds browsers cache preflight — reduces OPTIONS spam

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v) -> List[str]:
        """
        Accepts all three common .env formats:
          1. JSON array:      '["http://localhost:5173"]'
          2. Comma-separated: 'http://localhost:5173,https://app.com'
          3. Already a list:  passed through as-is (pydantic internal calls)
        Strips trailing slashes so http://localhost:5173/ and
        http://localhost:5173 don't create duplicate-origin mismatches.
        """
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError as e:
                    raise ValueError(f"CORS_ORIGINS is not valid JSON: {e}")
            else:
                parsed = [o.strip() for o in stripped.split(",") if o.strip()]
        elif isinstance(v, list):
            parsed = v
        else:
            raise ValueError(f"CORS_ORIGINS must be a list or string, got {type(v)}")

        # Normalise: strip trailing slashes, drop empty strings
        cleaned = [o.rstrip("/") for o in parsed if o]
        if not cleaned:
            raise ValueError(
                "CORS_ORIGINS resolved to an empty list. "
                "Set it in your .env, e.g.: "
                'CORS_ORIGINS=["http://localhost:5173"]'
            )
        return cleaned

    @field_validator("CORS_METHODS", "CORS_HEADERS", mode="before")
    @classmethod
    def parse_cors_lists(cls, v) -> List[str]:
        """Same JSON / CSV parsing for CORS_METHODS and CORS_HEADERS."""
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in stripped.split(",") if i.strip()]
        return v

    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60         # seconds
    RATE_LIMIT_BURST: int = 20

    # =========================================================================
    # MONITORING & LOGGING
    # =========================================================================
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"            # "json" | "text"

    # =========================================================================
    # BACKUP & RECOVERY
    # =========================================================================
    BACKUP_ENABLED: bool = True
    BACKUP_SCHEDULE: str = "0 2 * * *"
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_PATH: str = "/backups/postgres"

    # =========================================================================
    # HEALTH CHECKS
    # =========================================================================
    HEALTH_CHECK_INTERVAL: int = 30
    HEALTH_CHECK_TIMEOUT: int = 5

    # =========================================================================
    # CROSS-FIELD VALIDATION
    # =========================================================================
    @model_validator(mode="after")
    def production_safety_checks(self) -> "Settings":
        """
        Enforce stricter rules when ENVIRONMENT=production so misconfigurations
        are caught at startup rather than silently misbehaving in prod.
        """
        if self.ENVIRONMENT == "production":
            # Wildcard origins are dangerous in prod
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "CORS_ORIGINS cannot contain '*' in production. "
                    "Specify exact origins."
                )
            # Default secret key is insecure
            if self.SECRET_KEY == secrets.token_urlsafe(32):
                raise ValueError(
                    "SECRET_KEY must be explicitly set in production."
                )
            # Debug mode leaks stack traces
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production.")

        return self

    # =========================================================================
    # PYDANTIC CONFIG
    # =========================================================================
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",         # was "allow" — silently swallowing typos; now
    )                           # ignored so unknown keys don't pollute settings


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()