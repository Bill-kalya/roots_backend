from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
import re

from app.models.newsletter import NewsletterSubscriber

class NewsletterService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    async def subscribe(self, email: str) -> dict:
        """Subscribe an email to newsletter"""
        # Validate email
        if not self.validate_email(email):
            return {
                "success": False,
                "message": "Invalid email format",
                "already_subscribed": False
            }
        
        # Check if already subscribed
        query = select(NewsletterSubscriber).where(
            NewsletterSubscriber.email == email.lower()
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            if existing.is_confirmed:
                return {
                    "success": False,
                    "message": "Email already subscribed",
                    "already_subscribed": True
                }
            else:
                return {
                    "success": False,
                    "message": "Email already pending confirmation",
                    "already_subscribed": True
                }
        
        # Create new subscriber
        subscriber = NewsletterSubscriber(
            email=email.lower(),
            is_confirmed=False
        )
        
        self.db.add(subscriber)
        await self.db.commit()
        
        # TODO: Send confirmation email here
        # await self.send_confirmation_email(email)
        
        return {
            "success": True,
            "message": "Subscription successful. Please check your email to confirm.",
            "already_subscribed": False
        }
    
    async def confirm_subscription(self, email: str) -> bool:
        """Confirm a newsletter subscription"""
        query = select(NewsletterSubscriber).where(
            NewsletterSubscriber.email == email.lower()
        )
        result = await self.db.execute(query)
        subscriber = result.scalar_one_or_none()
        
        if not subscriber:
            return False
        
        if subscriber.is_confirmed:
            return True
        
        subscriber.is_confirmed = True
        await self.db.commit()
        
        return True
    
    async def unsubscribe(self, email: str) -> bool:
        """Unsubscribe from newsletter"""
        query = select(NewsletterSubscriber).where(
            NewsletterSubscriber.email == email.lower()
        )
        result = await self.db.execute(query)
        subscriber = result.scalar_one_or_none()
        
        if not subscriber:
            return False
        
        await self.db.delete(subscriber)
        await self.db.commit()
        
        return True
    
    async def get_subscribers(self, confirmed_only: bool = True) -> list:
        """Get all newsletter subscribers"""
        query = select(NewsletterSubscriber)
        
        if confirmed_only:
            query = query.where(NewsletterSubscriber.is_confirmed == True)
        
        query = query.order_by(NewsletterSubscriber.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_subscriber_count(self, confirmed_only: bool = True) -> int:
        """Get total number of subscribers"""
        query = select(NewsletterSubscriber)
        
        if confirmed_only:
            query = query.where(NewsletterSubscriber.is_confirmed == True)
        
        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        return result.scalar_one()