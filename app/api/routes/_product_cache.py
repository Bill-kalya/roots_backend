from __future__ import annotations

from typing import Any


async def invalidate_product_cache(redis: Any, product_id: str) -> None:
    """Invalidate product caches after create/update/delete."""
    await redis.delete(f"product:{product_id}")

    keys = await redis.keys("products:list:*")
    keys += await redis.keys("products:featured:*")
    if keys:
        await redis.delete(*keys)

