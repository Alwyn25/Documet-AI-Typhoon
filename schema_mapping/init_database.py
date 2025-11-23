"""Database initialization script for schema mapping service"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR.parent) not in sys.path:
    sys.path.append(str(ROOT_DIR.parent))

from app.utils.database import db_manager
from app.config import settings
from app.utils.logging import logger


async def main():
    """Initialize database tables"""
    print(f"Connecting to PostgreSQL database: {settings.POSTGRES_DB}")
    print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    
    try:
        await db_manager.connect()
        print("✓ Database connection established")
        
        await db_manager.initialize_tables()
        print("✓ Database tables initialized successfully")
        
        await db_manager.close()
        print("✓ Database connection closed")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        logger.log_error("database_init_script_failed", {"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

