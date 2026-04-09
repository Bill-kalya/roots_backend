from fastapi import APIRouter, Depends
from typing import Dict, Any
import asyncio
from datetime import datetime
from app.db.session import db_manager
from app.cache.redis_manager import redis_manager

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check for load balancers and k8s"""
    
    # Run checks concurrently
    db_health, redis_health = await asyncio.gather(
        db_manager.health_check(),
        redis_manager.health_check(),
        return_exceptions=True
    )
    
    status = "healthy"
    checks = {
        "database": db_health if not isinstance(db_health, Exception) else {"connected": False, "error": str(db_health)},
        "redis": redis_health if not isinstance(redis_health, Exception) else {"connected": False, "error": str(redis_health)},
    }
    
    # Determine overall status
    if not checks["database"].get("connected", False):
        status = "unhealthy"
    elif not checks["redis"].get("connected", False):
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "version": "1.0.0",
        "service": "roots-backend"
    }

@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe"""
    # Check if service is ready to accept traffic
    return {
        "ready": True,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe"""
    # Simple check that service is running
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    }