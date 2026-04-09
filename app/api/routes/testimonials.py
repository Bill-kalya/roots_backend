from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.db.session import get_db
from app.models.testimonial import Testimonial
from app.schemas.common import ResponseModel
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

router = APIRouter()

class TestimonialResponse(BaseModel):
    id: UUID
    name: str
    text: str
    location: str | None
    created_at: datetime

class TestimonialCreate(BaseModel):
    name: str
    text: str
    location: str | None = None

@router.get("/", response_model=List[TestimonialResponse])
async def get_testimonials(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get approved testimonials"""
    query = select(Testimonial).where(
        Testimonial.is_approved == True
    ).order_by(
        Testimonial.created_at.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    testimonials = result.scalars().all()
    
    return [
        TestimonialResponse(
            id=t.id,
            name=t.name,
            text=t.text,
            location=t.location,
            created_at=t.created_at
        )
        for t in testimonials
    ]

@router.post("/", response_model=ResponseModel)
async def create_testimonial(
    testimonial: TestimonialCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new testimonial (pending approval)"""
    new_testimonial = Testimonial(
        name=testimonial.name,
        text=testimonial.text,
        location=testimonial.location,
        is_approved=False  # Requires admin approval
    )
    
    db.add(new_testimonial)
    await db.commit()
    
    return ResponseModel(
        success=True,
        message="Testimonial submitted for approval",
        data=None
    )

# Admin endpoints
@router.get("/admin/pending", response_model=List[TestimonialResponse])
async def get_pending_testimonials(
    db: AsyncSession = Depends(get_db)
):
    """Get pending testimonials (admin only)"""
    # In production, add admin authentication
    query = select(Testimonial).where(
        Testimonial.is_approved == False
    ).order_by(Testimonial.created_at.desc())
    
    result = await db.execute(query)
    testimonials = result.scalars().all()
    
    return [
        TestimonialResponse(
            id=t.id,
            name=t.name,
            text=t.text,
            location=t.location,
            created_at=t.created_at
        )
        for t in testimonials
    ]

@router.patch("/admin/{testimonial_id}/approve")
async def approve_testimonial(
    testimonial_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Approve a testimonial (admin only)"""
    query = select(Testimonial).where(Testimonial.id == testimonial_id)
    result = await db.execute(query)
    testimonial = result.scalar_one_or_none()
    
    if not testimonial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonial not found"
        )
    
    testimonial.is_approved = True
    await db.commit()
    
    return ResponseModel(
        success=True,
        message="Testimonial approved successfully",
        data=None
    )

@router.delete("/admin/{testimonial_id}")
async def delete_testimonial(
    testimonial_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a testimonial (admin only)"""
    query = select(Testimonial).where(Testimonial.id == testimonial_id)
    result = await db.execute(query)
    testimonial = result.scalar_one_or_none()
    
    if not testimonial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonial not found"
        )
    
    await db.delete(testimonial)
    await db.commit()
    
    return ResponseModel(
        success=True,
        message="Testimonial deleted successfully",
        data=None
    )