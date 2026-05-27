from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from uuid import UUID, uuid4
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from redis import asyncio as aioredis
import json
import hashlib
import asyncio
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderResponse
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class InventoryReservation:
    """Inventory reservation system for order processing"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.reservation_ttl = 900  # 15 minutes
    
    async def reserve_inventory(
        self, 
        order_id: UUID, 
        items: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict]]:
        """Reserve inventory for order"""
        
        reservations = []
        failed_items = []
        
        for item in items:
            product_id = str(item["product_id"])
            quantity = item["quantity"]
            
            # Use Redis for inventory reservation
            reserve_key = f"inventory:reserve:{product_id}"
            stock_key = f"inventory:stock:{product_id}"
            
            # Check available stock
            available = await self.redis.get(stock_key)
            if not available:
                # Load from DB if not in cache
                available = await self._load_stock_from_db(product_id)
            
            available = int(available) if available else 0
            
            if available >= quantity:
                # Reserve inventory
                reserved = await self.redis.incrby(reserve_key, quantity)
                await self.redis.expire(reserve_key, self.reservation_ttl)
                
                # Update available stock
                await self.redis.decrby(stock_key, quantity)
                
                reservations.append({
                    "product_id": product_id,
                    "quantity": quantity,
                    "reservation_id": str(uuid4())
                })
            else:
                failed_items.append({
                    "product_id": product_id,
                    "requested": quantity,
                    "available": available
                })
        
        if failed_items:
            # Rollback reservations
            for reservation in reservations:
                await self.redis.decrby(f"inventory:reserve:{reservation['product_id']}", reservation["quantity"])
                await self.redis.incrby(f"inventory:stock:{reservation['product_id']}", reservation["quantity"])
            
            return False, failed_items
        
        # Store reservation for order
        await self.redis.setex(
            f"order:reservation:{order_id}",
            self.reservation_ttl,
            json.dumps(reservations)
        )
        
        return True, []
    
    async def commit_reservation(self, order_id: UUID):
        """Commit inventory reservation (after payment)"""
        
        reservation_key = f"order:reservation:{order_id}"
        reservations_data = await self.redis.get(reservation_key)
        
        if reservations_data:
            reservations = json.loads(reservations_data)
            
            # Move from reserved to sold
            for reservation in reservations:
                product_id = reservation["product_id"]
                quantity = reservation["quantity"]
                
                # Decrement actual stock in DB
                await self._decrement_stock_in_db(product_id, quantity)
                
                # Remove reservation
                await self.redis.decrby(f"inventory:reserve:{product_id}", quantity)
            
            # Clear reservation
            await self.redis.delete(reservation_key)
    
    async def release_reservation(self, order_id: UUID):
        """Release inventory reservation (if order fails/cancels)"""
        
        reservation_key = f"order:reservation:{order_id}"
        reservations_data = await self.redis.get(reservation_key)
        
        if reservations_data:
            reservations = json.loads(reservations_data)
            
            for reservation in reservations:
                product_id = reservation["product_id"]
                quantity = reservation["quantity"]
                
                # Release reserved inventory
                await self.redis.decrby(f"inventory:reserve:{product_id}", quantity)
                await self.redis.incrby(f"inventory:stock:{product_id}", quantity)
            
            await self.redis.delete(reservation_key)
    
    async def _load_stock_from_db(self, product_id: str) -> int:
        """Load stock from database"""
        # Implementation would query PostgreSQL
        return 0
    
    async def _decrement_stock_in_db(self, product_id: str, quantity: int):
        """Decrement stock in database"""
        # Implementation would update PostgreSQL
        pass

class OrderService:
    """Enterprise order service with idempotency, distributed transactions, and inventory management"""
    
    def __init__(self, db: AsyncSession, redis_client: aioredis.Redis):
        self.db = db
        self.redis = redis_client
        self.inventory = InventoryReservation(redis_client)
    
    async def create_order(
        self, 
        user_id: UUID, 
        order_data: OrderCreate,
        cart_items: List[Dict[str, Any]],
        idempotency_key: str = None
    ) -> Dict[str, Any]:
        """
        Create order with idempotency support and inventory reservation
        """
        
        # Check idempotency
        if idempotency_key:
            existing_order = await self._get_order_by_idempotency_key(idempotency_key)
            if existing_order:
                return existing_order
        
        if not cart_items:
            raise ValueError("Cannot create order with empty cart")
        
        # Calculate totals
        subtotal = sum(
            Decimal(str(item["price"])) * item["quantity"] 
            for item in cart_items
        )
        total = subtotal + order_data.shipping_fee
        
        # Generate order ID
        order_id = uuid4()
        
        # Reserve inventory
        reservation_success, failed_items = await self.inventory.reserve_inventory(
            order_id, 
            cart_items
        )
        
        if not reservation_success:
            raise ValueError(f"Insufficient stock for items: {failed_items}")
        
        # Create order with distributed transaction
        try:
            # Create order record
            order = Order(
                id=order_id,
                user_id=user_id,
                status=OrderStatus.PENDING,
                subtotal=subtotal,
                shipping_fee=order_data.shipping_fee,
                total=total
            )
            
            self.db.add(order)
            await self.db.flush()
            
            # Create order items with snapshots
            for cart_item in cart_items:
                order_item = OrderItem(
                    id=uuid4(),
                    order_id=order.id,
                    product_id=UUID(cart_item["product_id"]),
                    name_snapshot=cart_item["name"],
                    price_snapshot=Decimal(str(cart_item["price"])),
                    quantity=cart_item["quantity"]
                )
                self.db.add(order_item)
            
            # Store idempotency record
            if idempotency_key:
                await self._store_idempotency_key(idempotency_key, order_id)
            
            await self.db.commit()
            await self.db.refresh(order)
            
            # Schedule timeout job
            await self._schedule_order_timeout(order_id, timeout_minutes=15)
            
            # Clear user's cart
            await self._clear_user_cart(user_id)
            
            return {
                "order_id": order_id,
                "status": "pending",
                "requires_payment": True,
                "total": total,
                "reservation_expires_in": 900  # 15 minutes
            }
            
        except Exception as e:
            # Rollback inventory reservation
            await self.inventory.release_reservation(order_id)
            await self.db.rollback()
            raise e
    
    async def confirm_payment(self, order_id: UUID, payment_intent_id: str) -> Order:
        """Confirm payment and commit inventory"""
        
        order = await self.get_order_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if order.status != OrderStatus.PENDING:
            raise ValueError(f"Order cannot be paid. Current status: {order.status}")
        
        # Commit inventory reservation
        await self.inventory.commit_reservation(order_id)
        
        # Update order status + provider payment reference
        order.status = OrderStatus.PAID
        # This repo uses Order.payment_reference (not payment_intent_id)
        order.payment_reference = payment_intent_id
        order.paid_at = datetime.utcnow()

        
        await self.db.commit()
        await self.db.refresh(order)
        
        # Cancel timeout job
        await self._cancel_order_timeout(order_id)
        
        # Queue fulfillment job
        await self._queue_fulfillment(order_id)
        
        return order
    
    async def cancel_order(self, order_id: UUID, user_id: UUID, reason: str = None) -> Order:
        """Cancel order and release inventory"""
        
        order = await self.get_order_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if str(order.user_id) != str(user_id):
            raise ValueError("Not authorized to cancel this order")
        
        if order.status not in [OrderStatus.PENDING, OrderStatus.PAID]:
            raise ValueError(f"Cannot cancel order with status: {order.status}")
        
        # Release inventory if not yet committed
        if order.status == OrderStatus.PENDING:
            await self.inventory.release_reservation(order_id)
        
        # Update order status
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        order.cancellation_reason = reason
        
        await self.db.commit()
        await self.db.refresh(order)
        
        return order
    
    async def _schedule_order_timeout(self, order_id: UUID, timeout_minutes: int = 15):
        """Schedule order timeout job"""
        
        from app.workers.order_worker import cancel_expired_order
        cancel_expired_order.apply_async(
            args=[str(order_id)],
            countdown=timeout_minutes * 60
        )
        
        # Store in Redis for tracking
        await self.redis.setex(
            f"order:timeout:{order_id}",
            timeout_minutes * 60,
            datetime.utcnow().isoformat()
        )
    
    async def _cancel_order_timeout(self, order_id: UUID):
        """Cancel scheduled timeout"""
        
        await self.redis.delete(f"order:timeout:{order_id}")
        
        # Note: Celery tasks can't be easily cancelled, so we use a flag
        await self.redis.setex(f"order:paid:{order_id}", 3600, "true")
    
    async def _get_order_by_idempotency_key(self, key: str) -> Optional[Dict]:
        """Get existing order by idempotency key"""
        
        order_id = await self.redis.get(f"idempotency:{key}")
        if order_id:
            order = await self.get_order_by_id(UUID(order_id))
            if order:
                return {
                    "order_id": order.id,
                    "status": order.status.value,
                    "already_processed": True
                }
        return None
    
    async def _store_idempotency_key(self, key: str, order_id: UUID):
        """Store idempotency key"""
        
        await self.redis.setex(
            f"idempotency:{key}",
            86400 * 7,  # 7 days
            str(order_id)
        )
    
    async def _clear_user_cart(self, user_id: UUID):
        """Clear user's cart after order"""
        
        await self.redis.delete(f"cart:{user_id}")
        await self.redis.delete(f"cart:version:{user_id}")
    
    async def _queue_fulfillment(self, order_id: UUID):
        """Queue order fulfillment job"""
        
        from app.workers.order_worker import fulfill_order
        fulfill_order.apply_async(args=[str(order_id)], countdown=60)
    
    async def get_order_by_id(self, order_id: UUID) -> Optional[Order]:
        """Get order by ID"""
        
        query = select(Order).where(Order.id == order_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_order_with_items(self, order_id: UUID) -> Optional[Dict[str, Any]]:
        """Get order with its items"""
        
        order = await self.get_order_by_id(order_id)
        if not order:
            return None
        
        query = select(OrderItem).where(OrderItem.order_id == order_id)
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return {
            "order": order,
            "items": items
        }

# Background task for expired orders
async def process_expired_orders():
    """Background task to process expired pending orders"""
    
    while True:
        try:
            # Find expired orders
            expiry_time = datetime.utcnow() - timedelta(minutes=15)
            
            # Query expired orders
            # Implementation would query DB for pending orders older than expiry_time
            
            await asyncio.sleep(60)  # Run every minute
            
        except Exception as e:
            logger.error(f"Expired order processor error: {e}")
            await asyncio.sleep(60)