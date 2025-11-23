"""Main FastAPI application for validation service"""

import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes.validation import router as validation_router
from .utils.logging import logger
from .utils.database import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.log_step("starting_validation_service", {
        "host": settings.APP_HOST,
        "port": settings.APP_PORT,
        "debug": settings.DEBUG,
        "python_version": sys.version
    })
    
    logger.log_step("application_startup", {
        "app_name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION
    })
    
    # Initialize PostgreSQL database
    try:
        await db_manager.connect()
        logger.log_step("postgres_database_initialized", {"status": "success"})
    except Exception as e:
        logger.log_error("postgres_database_initialization_failed", {"error": str(e)})
        # Continue startup even if database fails (for development)
    
    yield
    
    # Shutdown
    await db_manager.close()
    logger.log_step("application_shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Validation Agent for comparing invoice entities with PostgreSQL database",
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
app.include_router(validation_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "endpoints": {
            "health": "/api/v1/health",
            "validate": "/api/v1/validate/",
            "validate_by_number": "/api/v1/validate/{invoice_number}",
            "docs": "/docs"
        }
    }

