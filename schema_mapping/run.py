import uvicorn

from app.config import settings

if __name__ == "__main__":
    host = settings.APP_HOST
    port = settings.APP_PORT
    debug = settings.DEBUG
    
    print(f"Starting {settings.SERVICE_NAME} on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"LLM Model: {settings.LLM_MODEL}")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )

