from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.services.newsletter_service import NewsletterService
from app.schemas.common import ResponseModel

router = APIRouter()

class NewsletterSubscribe(BaseModel):
    email: EmailStr

class NewsletterUnsubscribe(BaseModel):
    email: EmailStr

@router.post("/subscribe", response_model=ResponseModel)
async def subscribe_to_newsletter(
    subscription: NewsletterSubscribe,
    db: AsyncSession = Depends(get_db)
):
    """Subscribe to newsletter"""
    service = NewsletterService(db)
    result = await service.subscribe(subscription.email)
    
    if not result["success"]:
        if result.get("already_subscribed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return ResponseModel(
        success=True,
        message=result["message"],
        data=None
    )

@router.post("/confirm")
async def confirm_subscription(
    email: EmailStr,
    db: AsyncSession = Depends(get_db)
):
    """Confirm newsletter subscription (via email link)"""
    service = NewsletterService(db)
    success = await service.confirm_subscription(email)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    return {"success": True, "message": "Subscription confirmed successfully"}

@router.post("/unsubscribe", response_model=ResponseModel)
async def unsubscribe_from_newsletter(
    unsubscription: NewsletterUnsubscribe,
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from newsletter"""
    service = NewsletterService(db)
    success = await service.unsubscribe(unsubscription.email)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found in subscribers"
        )
    
    return ResponseModel(
        success=True,
        message="Unsubscribed successfully",
        data=None
    )

@router.get("/subscribers/count")
async def get_subscriber_count(
    db: AsyncSession = Depends(get_db)
):
    """Get total number of subscribers (public)"""
    service = NewsletterService(db)
    count = await service.get_subscriber_count(confirmed_only=True)
    
    return {"count": count}