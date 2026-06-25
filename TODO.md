- [ ] Fix merchant_payout_settings_001.py down_revision to point to 3b7c5c7d9f42
- [ ] Verify migration graph: alembic heads (single head: merchant_payout_settings_003)
- [ ] Verify history: alembic history (chain should show 3b7c5c7d9f42 -> merchant_payout_settings_001 -> 002 -> 003)
- [ ] Apply migrations locally: alembic upgrade head
- [ ] Verify current: alembic current (merchant_payout_settings_003)
- [ ] git commit + push

