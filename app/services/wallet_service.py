from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.merchant_wallet import MerchantWallet
from app.models.transaction_ledger import TransactionLedger, EntryType
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.core.config import settings

import logging

logger = logging.getLogger(__name__)


class WalletService:
    """Manages merchant wallet balances, escrow holds, and ledgers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_wallet(self, merchant_id: UUID, currency: str = "KES", for_update: bool = False) -> MerchantWallet:
        stmt = select(MerchantWallet).where(MerchantWallet.merchant_id == merchant_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        wallet = result.scalar_one_or_none()

        if not wallet:
            wallet = MerchantWallet(
                merchant_id=merchant_id,
                available_balance=Decimal("0.00"),
                pending_balance=Decimal("0.00"),
                total_earned=Decimal("0.00"),
                total_withdrawn=Decimal("0.00"),
                currency=currency,
            )
            self.db.add(wallet)
            await self.db.commit()
            await self.db.refresh(wallet)

        return wallet

    async def credit_pending_balance(
        self,
        merchant_id: UUID,
        amount: Decimal,
        order_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> MerchantWallet:
        """Credit merchant's pending balance on successful payment (escrow hold)."""
        wallet = await self.get_or_create_wallet(merchant_id, for_update=True)

        wallet.pending_balance += amount
        wallet.total_earned += amount

        ledger = TransactionLedger(
            merchant_id=merchant_id,
            wallet_id=wallet.id,
            amount=amount,
            entry_type=EntryType.CREDIT_PENDING.value,
            currency=wallet.currency,
            reference_id=str(order_id),
            reference_type="order",
            description=f"Payment received for order {order_id} (held in escrow)",
            actor_id=actor_id,
            ip_address=ip_address,
        )
        self.db.add(ledger)
        await self.db.commit()
        await self.db.refresh(wallet)

        logger.info("Credited pending %.2f %s to merchant %s (order %s)", amount, wallet.currency, merchant_id, order_id)
        return wallet

    async def release_to_available(self, merchant_id: UUID, amount: Decimal, order_id: UUID, actor_id: Optional[UUID] = None, ip_address: Optional[str] = None) -> MerchantWallet:
        """Release escrowed funds to available balance (e.g. after delivery).

        Protected against double-release: checks for an existing ESCROW_RELEASE
        ledger entry before modifying balances.
        """
        wallet = await self.get_or_create_wallet(merchant_id, for_update=True)

        existing = await self.db.execute(
            select(TransactionLedger).where(
                TransactionLedger.merchant_id == merchant_id,
                TransactionLedger.reference_id == str(order_id),
                TransactionLedger.reference_type == "order",
                TransactionLedger.entry_type == EntryType.ESCROW_RELEASE.value,
            )
        )
        if existing.scalar_one_or_none():
            logger.warning(
                "Escrow already released for merchant %s order %s — skipping",
                merchant_id, order_id,
            )
            return wallet

        if wallet.pending_balance < amount:
            raise ValueError(f"Insufficient pending balance. Have {wallet.pending_balance}, need {amount}")

        wallet.pending_balance -= amount
        wallet.available_balance += amount

        ledger = TransactionLedger(
            merchant_id=merchant_id,
            wallet_id=wallet.id,
            amount=amount,
            entry_type=EntryType.ESCROW_RELEASE.value,
            currency=wallet.currency,
            reference_id=str(order_id),
            reference_type="order",
            description=f"Funds released from escrow for order {order_id}",
            actor_id=actor_id,
            ip_address=ip_address,
        )
        self.db.add(ledger)
        await self.db.commit()
        await self.db.refresh(wallet)

        return wallet

    async def deduct_withdrawal(self, merchant_id: UUID, amount: Decimal, payout_id: UUID, actor_id: Optional[UUID] = None, ip_address: Optional[str] = None) -> MerchantWallet:
        """Deduct from available balance on payout."""
        wallet = await self.get_or_create_wallet(merchant_id, for_update=True)

        if wallet.available_balance < amount:
            raise ValueError(f"Insufficient available balance. Have {wallet.available_balance}, need {amount}")

        wallet.available_balance -= amount
        wallet.total_withdrawn += amount

        ledger = TransactionLedger(
            merchant_id=merchant_id,
            wallet_id=wallet.id,
            amount=amount,
            entry_type=EntryType.PAYOUT_REQUEST.value,
            currency=wallet.currency,
            reference_id=str(payout_id),
            reference_type="payout",
            description=f"Withdrawal initiated (payout {payout_id})",
            actor_id=actor_id,
            ip_address=ip_address,
        )
        self.db.add(ledger)
        await self.db.commit()
        await self.db.refresh(wallet)

        return wallet

    async def get_wallet(self, merchant_id: UUID) -> MerchantWallet:
        return await self.get_or_create_wallet(merchant_id)

    async def get_ledger(self, merchant_id: UUID, limit: int = 50) -> list[TransactionLedger]:
        stmt = (
            select(TransactionLedger)
            .where(TransactionLedger.merchant_id == merchant_id)
            .order_by(TransactionLedger.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def split_order_earnings(self, order_id: UUID) -> dict:
        """Calculate and credit each merchant's pending balance for an order."""
        order = await self.db.get(Order, order_id)
        if not order:
            raise ValueError("Order not found")

        stmt = select(OrderItem).where(OrderItem.order_id == order_id)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        merchant_shares: dict[UUID, Decimal] = {}
        for item in items:
            product = await self.db.get(Product, item.product_id)
            if not product or not product.merchant_id:
                continue
            merchant_id = product.merchant_id
            share = merchant_shares.get(merchant_id, Decimal("0.00"))
            share += item.price_snapshot * item.quantity
            merchant_shares[merchant_id] = share

        results = []
        for merchant_id, gross_share in merchant_shares.items():
            wallet = await self.credit_pending_balance(merchant_id, gross_share, order_id)
            results.append({
                "merchant_id": str(merchant_id),
                "gross_amount": gross_share,
                "pending_balance": wallet.pending_balance,
            })

        return {"order_id": str(order_id), "splits": results}
