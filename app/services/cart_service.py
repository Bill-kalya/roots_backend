import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from uuid import UUID
from datetime import datetime, timedelta
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.config import settings
from app.schemas.cart import CartItem, CartResponse
from app.models.product import Product
import logging

logger = logging.getLogger(__name__)

class CartService:
    """Enterprise cart service with Redis primary, PostgreSQL backup, and advanced features"""
    
    def __init__(self, redis_client: aioredis.Redis, db_session: AsyncSession = None):
        self.redis = redis_client
        self.db = db_session
        self.cart_ttl = getattr(settings, 'REDIS_CART_TTL', 604800)  # 7 days default
        self.abandoned_cart_ttl = 3600 * 24  # 24 hours for abandoned detection
    
    def _get_cart_key(self, user_id: UUID) -> str:
        return f"cart:{user_id}"
    
    def _get_cart_version_key(self, user_id: UUID) -> str:
        return f"cart:version:{user_id}"
    
    async def get_cart(self, user_id: UUID, use_cache: bool = True) -> CartResponse:
        """Get user's cart with optimistic locking"""
        
        # Try Redis first
        cart_key = self._get_cart_key(user_id)
        cart_data = await self.redis.get(cart_key)
        
        if cart_data and use_cache:
            cart = json.loads(cart_data)
            items = [CartItem(**item) for item in cart.get("items", [])]
        else:
            # Fallback to PostgreSQL
            items = await self._load_cart_from_db(user_id)
            cart = {"items": [item.dict() for item in items], "version": 1}
        
        total_items = sum(item.quantity for item in items)
        subtotal = sum(item.price * item.quantity for item in items)
        
        return CartResponse(
            items=items,
            total_items=total_items,
            subtotal=subtotal
        )
    
    async def set_cart_item(
        self, 
        user_id: UUID, 
        product_id: UUID, 
        quantity: int, 
        product_data: dict,
        use_version_check: bool = True
    ) -> CartResponse:
        """
        Set cart item quantity with optimistic concurrency control
        quantity == 0 removes the item
        """
        
        cart_key = self._get_cart_key(user_id)
        version_key = self._get_cart_version_key(user_id)
        
        # Get current version
        current_version = await self.redis.get(version_key)
        current_version = int(current_version) if current_version else 1
        
        # Use Redis WATCH for optimistic locking
        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(cart_key)
                
                # Get current cart
                cart_data = await pipe.get(cart_key)
                cart = json.loads(cart_data) if cart_data else {"items": [], "version": current_version}
                
                # Check version
                if use_version_check and cart.get("version", 1) != current_version:
                    raise ValueError("Cart was modified by another request. Please retry.")
                
                items = cart.get("items", [])
                
                if quantity == 0:
                    # Remove item
                    items = [item for item in items if item["product_id"] != str(product_id)]
                else:
                    # Find and update or add
                    found = False
                    for item in items:
                        if item["product_id"] == str(product_id):
                            item["quantity"] = quantity
                            item["price"] = float(product_data["price"])  # Update price
                            found = True
                            break
                    
                    if not found:
                        items.append({
                            "product_id": str(product_id),
                            "name": product_data["name"],
                            "price": float(product_data["price"]),
                            "quantity": quantity,
                            "image_url": product_data["image_url"],
                            "origin": product_data["origin"]
                        })
                
                # Update version
                new_version = current_version + 1
                cart["items"] = items
                cart["version"] = new_version
                cart["updated_at"] = datetime.utcnow().isoformat()
                
                # Execute transaction
                pipe.multi()
                await pipe.setex(cart_key, self.cart_ttl, json.dumps(cart))
                await pipe.setex(version_key, self.cart_ttl, str(new_version))
                await pipe.execute()
                
                # Async backup to PostgreSQL
                asyncio.create_task(self._sync_cart_to_db(user_id, items))
                
                return await self.get_cart(user_id)
                
            except Exception as e:
                logger.error(f"Cart update failed for user {user_id}: {e}")
                raise
    
    async def merge_carts(self, user_id: UUID, anonymous_cart: Dict) -> CartResponse:
        """Merge anonymous cart with user cart after login"""
        
        user_cart = await self.get_cart(user_id)
        anonymous_items = anonymous_cart.get("items", [])
        
        # Merge items
        merged_items = {str(item.product_id): item for item in user_cart.items}
        
        for anon_item in anonymous_items:
            product_id = anon_item["product_id"]
            if product_id in merged_items:
                # Combine quantities
                merged_items[product_id].quantity += anon_item["quantity"]
            else:
                # Add new item
                merged_items[product_id] = CartItem(**anon_item)
        
        # Update cart with merged items
        cart_key = self._get_cart_key(user_id)
        version_key = self._get_cart_version_key(user_id)
        
        new_cart = {
            "items": [item.dict() for item in merged_items.values()],
            "version": 1,
            "merged_at": datetime.utcnow().isoformat()
        }
        
        await self.redis.setex(cart_key, self.cart_ttl, json.dumps(new_cart))
        await self.redis.setex(version_key, self.cart_ttl, "1")
        
        # Clear anonymous cart
        await self.redis.delete(f"cart:anonymous:{anonymous_cart.get('session_id', '')}")
        
        return await self.get_cart(user_id)
    
    async def remove_cart_item(self, user_id: UUID, product_id: UUID) -> CartResponse:
        """Remove item from cart"""
        return await self.set_cart_item(user_id, product_id, 0, {})
    
    async def clear_cart(self, user_id: UUID) -> CartResponse:
        """Clear entire cart"""
        cart_key = self._get_cart_key(user_id)
        version_key = self._get_cart_version_key(user_id)
        
        await self.redis.delete(cart_key)
        await self.redis.delete(version_key)
        
        # Clear from DB
        if self.db:
            from app.models.cart import CartItem as DBCartItem
            await self.db.execute(
                update(DBCartItem).where(DBCartItem.user_id == user_id).values(quantity=0)
            )
            await self.db.commit()
        
        return CartResponse(items=[], total_items=0, subtotal=Decimal("0.00"))
    
    async def _load_cart_from_db(self, user_id: UUID) -> List[CartItem]:
        """Load cart from PostgreSQL backup"""
        if not self.db:
            return []
        
        from app.models.cart import CartItem as DBCartItem
        
        query = select(DBCartItem).where(
            DBCartItem.user_id == user_id,
            DBCartItem.quantity > 0
        )
        result = await self.db.execute(query)
        db_items = result.scalars().all()
        
        items = []
        for db_item in db_items:
            items.append(CartItem(
                product_id=db_item.product_id,
                name=db_item.product_name,
                price=db_item.price,
                quantity=db_item.quantity,
                image_url=db_item.image_url,
                origin=db_item.origin
            ))
        
        return items
    
    async def _sync_cart_to_db(self, user_id: UUID, items: List[Dict]):
        """Async sync cart to PostgreSQL for backup"""
        if not self.db:
            return
        
        try:
            from app.models.cart import CartItem as DBCartItem
            
            # Delete existing items
            await self.db.execute(
                update(DBCartItem).where(DBCartItem.user_id == user_id).values(quantity=0)
            )
            
            # Insert new items
            for item in items:
                db_item = DBCartItem(
                    user_id=user_id,
                    product_id=UUID(item["product_id"]),
                    product_name=item["name"],
                    price=Decimal(str(item["price"])),
                    quantity=item["quantity"],
                    image_url=item["image_url"],
                    origin=item["origin"]
                )
                self.db.add(db_item)
            
            await self.db.commit()
            logger.debug(f"Cart synced to DB for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to sync cart to DB: {e}")
    
    async def get_abandoned_carts(self, older_than_minutes: int = 60) -> List[Dict]:
        """Find abandoned carts for recovery"""
        
        pattern = "cart:*"
        keys = await self.redis.keys(pattern)
        
        abandoned = []
        for key in keys:
            if key.startswith("cart:version:"):
                continue
            
            cart_data = await self.redis.get(key)
            if cart_data:
                cart = json.loads(cart_data)
                updated_at = cart.get("updated_at")
                
                if updated_at:
                    updated_time = datetime.fromisoformat(updated_at)
                    if datetime.utcnow() - updated_time > timedelta(minutes=older_than_minutes):
                        user_id = key.replace("cart:", "")
                        abandoned.append({
                            "user_id": user_id,
                            "items_count": len(cart.get("items", [])),
                            "updated_at": updated_at
                        })
        
        return abandoned
    
    async def send_abandoned_cart_reminders(self):
        """Send reminders for abandoned carts"""
        abandoned = await self.get_abandoned_carts(older_than_minutes=30)
        
        for cart_info in abandoned:
            # Queue email task
            from app.workers.email_worker import send_abandoned_cart_reminder
            send_abandoned_cart_reminder.delay(cart_info["user_id"])
            
            # Mark as reminded
            await self.redis.setex(
                f"cart:reminded:{cart_info['user_id']}",
                86400,  # 24 hours
                datetime.utcnow().isoformat()
            )
    
    async def expire_carts(self, older_than_days: int = 7):
        """Expire old carts"""
        pattern = "cart:*"
        keys = await self.redis.keys(pattern)
        
        expired_count = 0
        for key in keys:
            if key.startswith("cart:version:"):
                continue
            
            ttl = await self.redis.ttl(key)
            if ttl <= 0:
                await self.redis.delete(key)
                expired_count += 1
        
        logger.info(f"Expired {expired_count} old carts")
        return expired_count