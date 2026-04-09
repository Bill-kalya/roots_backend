from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, Token, TokenRefresh, UserResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, get_redis

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register new user"""
    service = AuthService(db)
    user = await service.register_user(user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    return user

@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Login user"""
    service = AuthService(db)
    user = await service.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    tokens = await service.create_tokens(user.id, redis)
    return tokens

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Refresh access token"""
    service = AuthService(db)
    tokens = await service.refresh_tokens(refresh_data.refresh_token, redis)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    return tokens

@router.post("/logout")
async def logout(
    current_user = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Logout user (blacklist tokens)"""
    # In a real implementation, you'd blacklist the current token
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user)):
    """Get current user info"""
    return current_user