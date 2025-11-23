import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routes.ingestion import router as ingestion_router
from .utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_step("starting_ingestion_service", {
        "host": settings.APP_HOST,
        "port": settings.APP_PORT,
        "debug": settings.DEBUG,
        "python_version": sys.version,
        "storage_root": str(settings.storage_root_path)
    })

    settings.storage_root_path.mkdir(parents=True, exist_ok=True)
    logger.log_step("storage_directory_ready", {
        "storage_root": str(settings.storage_root_path)
    })

    yield

    logger.log_step("ingestion_service_shutdown")


app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Document ingestion microservice for uploading and storing source files.",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.log_error("unhandled_exception", {
        "method": request.method,
        "url": str(request.url),
        "error": str(exc)
    })

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


app.include_router(ingestion_router)


@app.get("/")
async def root():
    return {
        "message": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "endpoints": {
            "health": "/api/v1/health",
            "ingestion": "/api/v1/ingestion/",
            "docs": "/docs"
        }
    }


