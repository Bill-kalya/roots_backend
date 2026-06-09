"""baseline_initial_schema

Revision ID: baseline_initial_schema_real
Revises: 039a39ad563e
Create Date: 2026-06-09 17:03:13.302719

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'baseline_initial_schema_real'
down_revision = '039a39ad563e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean baseline: create the full schema needed by the app.
    # This intentionally uses explicit DDL (not autogenerate) so Railway fresh DBs work.

    # Enable uuid generation (Postgres). Safe if already exists.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # users
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='users') THEN
                CREATE TABLE users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) NOT NULL UNIQUE,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    role userrole NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                    verification_token VARCHAR(255),
                    verification_token_expires TIMESTAMP,
                    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                    last_failed_login TIMESTAMP,
                    account_locked_until TIMESTAMP,
                    lockout_reason VARCHAR(255),
                    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    mfa_secret VARCHAR(255),
                    last_login TIMESTAMP,
                    last_login_ip VARCHAR(45),
                    last_login_user_agent VARCHAR(500),
                    merchant_approved BOOLEAN NOT NULL DEFAULT FALSE,
                    merchant_details JSON,
                    store_name VARCHAR(255),
                    store_description TEXT,
                    password_reset_token VARCHAR(255),
                    password_reset_expires TIMESTAMP,
                    password_updated_at TIMESTAMP,
                    previous_passwords JSON,
                    created_by_ip VARCHAR(45),
                    account_created_at TIMESTAMP DEFAULT now(),
                    last_activity TIMESTAMP DEFAULT now()
                );

                CREATE UNIQUE INDEX ix_users_email ON users(email);
            END IF;
        END $$;
        """
    )

    # userrole enum
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE userrole AS ENUM ('USER','MERCHANT','ADMIN');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # products
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            merchant_id UUID,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            long_description TEXT,
            price NUMERIC(10,2) NOT NULL,
            image_url VARCHAR(500) NOT NULL,
            gallery TEXT[],
            origin VARCHAR(100) NOT NULL,
            tag VARCHAR(100),
            stock INTEGER NOT NULL DEFAULT 0,
            is_featured BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            artisan VARCHAR(255),
            weight VARCHAR(100),
            dimensions VARCHAR(100),
            year INTEGER,
            materials TEXT[],
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname='products_merchant_id_fkey'
            ) THEN
                ALTER TABLE products
                ADD CONSTRAINT products_merchant_id_fkey
                FOREIGN KEY (merchant_id) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_products_merchant_id ON products(merchant_id);
        """
    )

    # orders
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='orders') THEN
                CREATE TABLE orders (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    subtotal NUMERIC(10,2) NOT NULL,
                    shipping_fee NUMERIC(10,2) DEFAULT 0,
                    total NUMERIC(10,2) NOT NULL,
                    payment_provider VARCHAR(50),
                    payment_reference VARCHAR(255),
                    paid_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    cancellation_reason VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    CONSTRAINT fk_orders_user_id_users FOREIGN KEY (user_id) REFERENCES users(id)
                );
            END IF;
        END $$;
        """
    )

    # order_items
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='order_items') THEN
                CREATE TABLE order_items (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_id UUID NOT NULL,
                    product_id UUID NOT NULL,
                    name_snapshot VARCHAR(255) NOT NULL,
                    price_snapshot NUMERIC(10,2) NOT NULL,
                    quantity INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP NOT NULL DEFAULT now(),
                    CONSTRAINT fk_order_items_order_id_orders FOREIGN KEY (order_id) REFERENCES orders(id)
                );
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname='fk_order_items_product_id_products'
            ) THEN
                ALTER TABLE order_items
                ADD CONSTRAINT fk_order_items_product_id_products
                FOREIGN KEY (product_id) REFERENCES products(id);
            END IF;
        END $$;
        """
    )

    # payments
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='payments') THEN
                CREATE TABLE payments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_id UUID,
                    provider VARCHAR(50) NOT NULL,
                    provider_transaction_id VARCHAR(255) UNIQUE,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    amount NUMERIC(10,2) NOT NULL,
                    currency VARCHAR(10) NOT NULL DEFAULT 'KES',
                    phone VARCHAR(20),
                    checkout_request_id VARCHAR(255) UNIQUE,
                    mpesa_receipt VARCHAR(100),
                    result_code VARCHAR(10),
                    raw_payload TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    CONSTRAINT fk_payments_order_id_orders FOREIGN KEY (order_id) REFERENCES orders(id)
                );

                CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status);
                CREATE INDEX IF NOT EXISTS ix_payments_order_id ON payments(order_id);
            END IF;
        END $$;
        """
    )

    # audit_logs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID,
            action VARCHAR(100) NOT NULL,
            resource VARCHAR(100) NOT NULL,
            resource_id VARCHAR(255),
            details JSON,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            status VARCHAR(20) NOT NULL,
            error_message VARCHAR(1000),
            created_at TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_action ON audit_logs(user_id, action);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource, resource_id);")



def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

