"""PostgreSQL database connection and management"""

import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from ..config import settings
from ..utils.logging import logger


class DatabaseManager:
    """PostgreSQL database manager for schema mapping service"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._connection_string = self._build_connection_string()

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string"""
        return (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )

    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                min_size=1,
                max_size=10
            )
            logger.log_step("postgres_connection_pool_created", {
                "host": settings.POSTGRES_HOST,
                "database": settings.POSTGRES_DB,
                "status": "success"
            })
        except Exception as e:
            logger.log_error("postgres_connection_failed", {"error": str(e)})
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.log_step("postgres_connection_pool_closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as connection:
            yield connection

    async def execute_query(self, query: str, *args):
        """Execute a query and return results"""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)

    async def execute_command(self, command: str, *args):
        """Execute a command (INSERT, UPDATE, DELETE)"""
        async with self.get_connection() as conn:
            return await conn.execute(command, *args)

    async def initialize_tables(self):
        """Initialize database tables if they don't exist"""
        create_tables_sql = """
        -- Create invoice table (main table)
        CREATE TABLE IF NOT EXISTS invoice (
            invoice_id SERIAL PRIMARY KEY,
            invoice_number VARCHAR(100),
            invoice_date DATE,
            due_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create partial unique index for invoice_number (allows NULL, but unique for non-NULL values)
        CREATE UNIQUE INDEX IF NOT EXISTS unique_invoice_number 
        ON invoice (invoice_number) 
        WHERE invoice_number IS NOT NULL;

        -- Create vendorinfo table
        CREATE TABLE IF NOT EXISTS vendorinfo (
            vendor_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            name VARCHAR(255),
            gstin VARCHAR(50),
            pan VARCHAR(50),
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_id)
        );

        -- Create customerinfo table
        CREATE TABLE IF NOT EXISTS customerinfo (
            customer_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            name VARCHAR(255),
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_id)
        );

        -- Create item_details table
        CREATE TABLE IF NOT EXISTS item_details (
            item_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            quantity DECIMAL(10, 2) NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            tax_percent DECIMAL(5, 2) NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Create Totals table
        CREATE TABLE IF NOT EXISTS Totals (
            totals_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            subtotal DECIMAL(10, 2) NOT NULL,
            gst_amount DECIMAL(10, 2) NOT NULL,
            round_off DECIMAL(10, 2),
            grand_total DECIMAL(10, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_id)
        );

        -- Create Paymentinfo table
        CREATE TABLE IF NOT EXISTS Paymentinfo (
            payment_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            mode VARCHAR(100),
            reference VARCHAR(255),
            status VARCHAR(20) CHECK (status IN ('Paid', 'Unpaid', 'Partial')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_id)
        );

        -- Create metadata table
        CREATE TABLE IF NOT EXISTS metadata (
            metadata_id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id) ON DELETE CASCADE,
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            extracted_confidence_score DECIMAL(5, 2),
            document_id VARCHAR(255),
            ocr_text TEXT,
            validation_is_valid BOOLEAN,
            validation_errors JSONB,
            validation_warnings JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_id)
        );

        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoice(invoice_number);
        CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoice(invoice_date);
        CREATE INDEX IF NOT EXISTS idx_vendor_gstin ON vendorinfo(gstin);
        CREATE INDEX IF NOT EXISTS idx_vendor_pan ON vendorinfo(pan);
        CREATE INDEX IF NOT EXISTS idx_item_invoice ON item_details(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_metadata_document_id ON metadata(document_id);
        """
        
        try:
            async with self.get_connection() as conn:
                await conn.execute(create_tables_sql)
            logger.log_step("database_tables_initialized", {"status": "success"})
        except Exception as e:
            logger.log_error("database_initialization_failed", {"error": str(e)})
            raise


# Global database manager instance
db_manager = DatabaseManager()

