from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile

from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID, uuid4
from pathlib import Path
import os

from app.db.session import get_db

from app.core.dependencies import require_merchant
from app.models.user import User
from app.models.product import Product
from app.schemas.product import ProductResponse
from app.services.product_service import ProductService
from app.core.config import settings
from app.utils.file_upload import save_upload_image, validate_upload_file
import json


router = APIRouter()

# Local filesystem upload target (served by FastAPI via /uploads)
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()


def _parse_json_array(v: Optional[str]) -> list[str]:
    """Parse frontend JSON array fields for materials/gallery.

    Frontend sometimes sends the literal string "NaN" for empty numeric values,
    which breaks json.loads(). Treat those as empty arrays.
    """
    if not v:
        return []

    if isinstance(v, str) and v.strip().lower() in {"nan", "null", "none"}:
        return []

    try:
        parsed = json.loads(v)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON array: {e}")

    return parsed if parsed is not None else []



def _parse_int_form(v: Optional[str], field_name: str, *, required: bool = True, default: Optional[int] = None) -> Optional[int]:
    if v is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return default
    if isinstance(v, str) and v.strip().lower() in {"", "nan", "null", "none"}:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")


def _parse_float_form(v: Optional[str], field_name: str, *, required: bool = True, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return default
    if isinstance(v, str) and v.strip().lower() in {"", "nan", "null", "none"}:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}")


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    description: str = Form(...),
    long_description: Optional[str] = Form(None),
    price: str = Form(...),
    origin: str = Form(...),
    tag: Optional[str] = Form(None),
    stock: str = Form(...),
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

    import logging

    logger = logging.getLogger(__name__)
    logger.info("Entered create_product")

    await validate_upload_file(image)
    image_url = await save_upload_image(image)


    parsed_materials = _parse_json_array(materials)
    parsed_gallery = _parse_json_array(gallery)

    parsed_price = _parse_float_form(price, "price")
    parsed_stock = _parse_int_form(stock, "stock")
    parsed_year = _parse_int_form(year, "year", required=False, default=None)

    if parsed_price is None or parsed_stock is None:
        raise HTTPException(status_code=400, detail="Invalid price or stock")

    new_product = Product(

        merchant_id=current_user.id,
        name=name,
        description=description,
        long_description=long_description,
        price=parsed_price,
        image_url=image_url,
        gallery=parsed_gallery,
        origin=origin,
        tag=tag,
        stock=parsed_stock,
        is_featured=is_featured,
        is_active=True,
        artisan=artisan,
        weight=weight,
        dimensions=dimensions,
        year=parsed_year,
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
    products, _ = await service.get_merchant_products(
        merchant_id=current_user.id
    )
    return [ProductResponse.model_validate(p) for p in products]


@router.put("/{product_id}", response_model=ProductResponse)
async def update_merchant_product(
    product_id: UUID,
    name: str = Form(...),
    description: str = Form(...),
    long_description: Optional[str] = Form(None),
    price: str = Form(...),
    origin: str = Form(...),
    tag: Optional[str] = Form(None),
    stock: str = Form(...),
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

    if product.merchant_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to modify this product")

    parsed_materials = _parse_json_array(materials)
    parsed_gallery = _parse_json_array(gallery)

    product.name = name
    product.description = description
    product.long_description = long_description

    parsed_price = _parse_float_form(price, "price")
    parsed_stock = _parse_int_form(stock, "stock")
    parsed_year = _parse_int_form(year, "year", required=False, default=None)

    if parsed_price is None or parsed_stock is None:
        raise HTTPException(status_code=400, detail="Invalid price or stock")

    product.price = parsed_price

    product.origin = origin
    product.tag = tag
    product.stock = parsed_stock

    product.is_featured = is_featured

    product.artisan = artisan
    product.weight = weight
    product.dimensions = dimensions
    product.year = _parse_int_form(year, "year", required=False, default=None)

    product.materials = parsed_materials
    product.gallery = parsed_gallery

    if image is not None:
        await validate_upload_file(image)
        product.image_url = await save_upload_image(image)

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
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.merchant_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this product")

    await db.delete(product)
    await db.commit()
    return {"message": f"Product {product_id} deleted successfully"}

