import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes.ocr import router as ocr_router
from .utils.logging import logger
from .utils.mongo import mongo_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.log_step("starting_ocr_agent", {
        "host": settings.APP_HOST,
        "port": settings.APP_PORT,
        "debug": settings.DEBUG,
        "python_version": sys.version
    })
    
    logger.log_step("application_startup", {
        "app_name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION
    })
    
    # Test MongoDB connection
    try:
        mongo_manager.client.admin.command('ping')
        logger.log_step("mongodb_connection_test", {"status": "success"})
    except Exception as e:
        logger.log_error("mongodb_connection_test_failed", {"error": str(e)})
        raise
    
    yield
    
    # Shutdown
    logger.log_step("application_shutdown")
    mongo_manager.close()


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="OCR Agent for text extraction using Azure Document Intelligence, Tesseract, and EasyOCR",
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
    
    return HTTPException(
        status_code=500,
        detail="Internal server error"
    )


# Include routers
app.include_router(ocr_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "endpoints": {
            "health": "/api/v1/health",
            "ocr": "/api/v1/ocr/",
            "documents": "/api/v1/documents/",
            "docs": "/docs"
        }
    } 