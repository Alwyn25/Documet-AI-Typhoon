import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes.schema_mapping import router as schema_mapping_router
from .utils.logging import logger
from .utils.database import db_manager
from .utils.mongo import mongo_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.log_step("starting_schema_mapping_service", {
        "host": settings.APP_HOST,
        "port": settings.APP_PORT,
        "debug": settings.DEBUG,
        "python_version": sys.version
    })
    
    logger.log_step("application_startup", {
        "app_name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "llm_model": settings.LLM_MODEL,
        "openai_api_key_set": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip()),
        "openai_api_key_length": len(settings.OPENAI_API_KEY.strip()) if settings.OPENAI_API_KEY else 0
    })
    
    # Initialize PostgreSQL database
    try:
        await db_manager.connect()
        await db_manager.initialize_tables()
        logger.log_step("postgres_database_initialized", {"status": "success"})
    except Exception as e:
        logger.log_error("postgres_database_initialization_failed", {"error": str(e)})
        # Continue startup even if database fails (for development)
    
    # MongoDB is initialized automatically when mongo_manager is imported
    # Test MongoDB connection
    try:
        mongo_manager.client.admin.command('ping')
        logger.log_step("mongodb_initialized", {"status": "success"})
    except Exception as e:
        logger.log_error("mongodb_initialization_failed", {"error": str(e)})
        # Continue startup even if MongoDB fails (for development)
    
    yield
    
    # Shutdown
    await db_manager.close()
    mongo_manager.close()
    logger.log_step("application_shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Schema Mapping Agent for extracting structured data from OCR text using LLM",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.log_step("request_completed", {
        "method": request.method,
        "url": str(request.url),
        "status_code": response.status_code,
        "process_time": process_time
    })
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.log_error("unhandled_exception", {
        "method": request.method,
        "url": str(request.url),
        "error": str(exc)
    })
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(schema_mapping_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "endpoints": {
            "health": "/api/v1/health",
            "schema_mapping": "/api/v1/schema-mapping/",
            "docs": "/docs"
        }
    }

