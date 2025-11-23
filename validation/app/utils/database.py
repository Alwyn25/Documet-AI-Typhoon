"""PostgreSQL database connection and management for validation service"""

import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from ..config import settings
from ..utils.logging import logger


class DatabaseManager:
    """PostgreSQL database manager for validation service"""

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


# Global database manager instance
db_manager = DatabaseManager()

