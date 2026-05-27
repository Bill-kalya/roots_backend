from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile

from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID, uuid4
from pathlib import Path
import os

from urllib.parse import quote

from app.db.session import get_db
from app.core.dependencies import require_merchant
from app.models.user import User
from app.models.product import Product
from app.schemas.product import ProductResponse
from app.services.product_service import ProductService
from app.core.config import settings
import json


router = APIRouter()

# Local filesystem upload target (served by FastAPI via /uploads)
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()


def _parse_json_array(v: Optional[str]) -> list[str]:
    if not v:
        return []
    try:
        parsed = json.loads(v)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON array: {e}")
    return parsed if parsed is not None else []


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    description: str = Form(...),
    long_description: Optional[str] = Form(None),
    price: float = Form(...),
    origin: str = Form(...),
    tag: Optional[str] = Form(None),
    stock: int = Form(...),
    is_featured: bool = Form(False),
    artisan: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    dimensions: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    materials: Optional[str] = Form(None),  # JSON string from frontend
    gallery: Optional[str] = Form(None),  # JSON string from frontend
    image: UploadFile = File(...),
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new product (Merchant only)."""

    ext = Path(image.filename).suffix or ".jpg"
    safe_name = f"{uuid4().hex}{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADS_DIR / safe_name

    contents = await image.read()
    file_path.write_bytes(contents)

    image_url = f"{settings.PUBLIC_API_BASE_URL}/uploads/{quote(safe_name)}"

    parsed_materials = _parse_json_array(materials)
    parsed_gallery = _parse_json_array(gallery)

    new_product = Product(
        name=name,
        description=description,
        long_description=long_description,
        price=price,
        image_url=image_url,
        gallery=parsed_gallery,
        origin=origin,
        tag=tag,
        stock=stock,
        is_featured=is_featured,
        is_active=True,
        artisan=artisan,
        weight=weight,
        dimensions=dimensions,
        year=year,
        materials=parsed_materials,
    )

    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)

    return ProductResponse.model_validate(new_product)


@router.get("", response_model=List[ProductResponse])
@router.get("/", response_model=List[ProductResponse])
async def get_merchant_products(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Get merchant's products."""
    service = ProductService(db)
    from app.schemas.common import PaginationParams

    params = PaginationParams(page=1, limit=100)
    products, _ = await service.get_products(params)
    return [ProductResponse.model_validate(p) for p in products]


@router.put("/{product_id}", response_model=ProductResponse)
async def update_merchant_product(
    product_id: UUID,
    name: str = Form(...),
    description: str = Form(...),
    long_description: Optional[str] = Form(None),
    price: float = Form(...),
    origin: str = Form(...),
    tag: Optional[str] = Form(None),
    stock: int = Form(...),
    is_featured: bool = Form(False),
    artisan: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    dimensions: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    materials: Optional[str] = Form(None),  # JSON string from frontend
    gallery: Optional[str] = Form(None),  # JSON string from frontend
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Update merchant's product."""

    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    parsed_materials = _parse_json_array(materials)
    parsed_gallery = _parse_json_array(gallery)

    product.name = name
    product.description = description
    product.long_description = long_description
    product.price = price
    product.origin = origin
    product.tag = tag
    product.stock = stock
    product.is_featured = is_featured
    product.artisan = artisan
    product.weight = weight
    product.dimensions = dimensions
    product.year = year
    product.materials = parsed_materials
    product.gallery = parsed_gallery

    if image is not None:
        ext = Path(image.filename).suffix or ".jpg"
        safe_name = f"{uuid4().hex}{ext}"
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOADS_DIR / safe_name

        contents = await image.read()
        file_path.write_bytes(contents)

        product.image_url = f"{settings.PUBLIC_API_BASE_URL}/uploads/{quote(safe_name)}"

    await db.commit()
    await db.refresh(product)

    return ProductResponse.model_validate(product)


@router.delete("/{product_id}")
async def delete_merchant_product(
    product_id: UUID,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Delete merchant's product."""
    # NOTE: implement DB delete + cache invalidation when merchant ownership is wired.
    return {"message": f"Delete product {product_id}"}

