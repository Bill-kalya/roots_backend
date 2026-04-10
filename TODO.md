# Fix DB Session Error in add_role_to_users.py

## Steps:
- [x] Step 1: Analyzed files (add_role_to_users.py, app/db/session.py, app/core/config.py)
- [x] Step 2: Created detailed edit plan and got user approval
- [x] Step 3: Created TODO.md 
- [x] Step 4: Updated add_role_to_users.py with db_manager.init()
- [x] Step 5: ✅ FIXED TypeError! DB initializes successfully. Now handling "users.role does not exist" - running Alembic migration
- [ ] Step 6: Re-test dry-run after migration
- [ ] Step 7: Run main to add roles
- [ ] Step 8: Complete task

**Status:** DB init fixed. Applying schema migration...
