import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import inspections, camera, inference, webcam_camera, sensor_inspection, settings
from endpoints.file_api import router as file_api_router
from endpoints.streaming_endpoints import router as streaming_router
from endpoints.streaming_config import router as streaming_config_router
from endpoints.streaming_monitoring import router as streaming_monitoring_router
from endpoints.streaming_admin import router as streaming_admin_router
from inspections_watcher_task import inspections_watcher_task
from starlette.staticfiles import StaticFiles
from db.engine import initialize_database
from app_config import APP_CONFIG
from logging_config import logging_config, get_logger

# Initialize logging system
logging_config.setup_logging()
logger = get_logger(__name__)

if not os.path.exists(APP_CONFIG['upload_folder_inspection']):
    os.makedirs(APP_CONFIG['upload_folder_inspection'])
    logger.info(f"Created upload directory: {APP_CONFIG['upload_folder_inspection']}")

#create database tables
initialize_database()
logger.info("Database tables initialized")

# create FastAPI Instance
app = FastAPI()
logger.info("FastAPI application instance created")

# Add a simple health check endpoint for network testing
@app.get("/health")
async def health_check():
    logger.debug("Health check endpoint accessed")
    return {"status": "ok", "message": "Backend is running and accessible"}

@app.get("/api/health")
async def api_health_check():
    logger.debug("API health check endpoint accessed")
    return {"status": "ok", "message": "API is running and accessible"}
app.include_router(inspections.router)
app.include_router(camera.router, prefix="/api")
app.include_router(webcam_camera.router, prefix="/api")
app.include_router(inference.router, prefix="/api")
app.include_router(sensor_inspection.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(file_api_router) # File API router already has /api prefix
app.include_router(streaming_router) # Streaming endpoints
app.include_router(streaming_config_router) # Streaming configuration endpoints
app.include_router(streaming_monitoring_router) # Streaming monitoring endpoints
app.include_router(streaming_admin_router) # Streaming administration endpoints

logger.info("All API routers registered successfully")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

logger.info("CORS middleware configured")

app.mount("/data", StaticFiles(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")), name="data")
logger.info("Static files mounted at /data")

if __name__ == "__main__":
    import uvicorn
    import asyncio

    async def main():
        logger.info("Starting application main function")
        
        # バックエンドサーバーのタスク
        async def start_fastapi():
            logger.info("Starting FastAPI server on 0.0.0.0:8000")
            config = uvicorn.Config(app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()

        # 他のタスク
        async def background_task():
            logger.info("Starting inspections watcher background task")
            try:
                await inspections_watcher_task()
            except Exception as e:
                logger.error(f"Inspections watcher task failed: {e}", exc_info=True)
        
        # Start streaming monitoring services
        async def start_streaming_monitoring():
            logger.info("Starting streaming monitoring services")
            try:
                from streaming.monitoring import start_monitoring
                await start_monitoring()
            except Exception as e:
                logger.warning(f"Failed to start streaming monitoring: {e}")

        task1 = asyncio.create_task(start_fastapi())
        task2 = asyncio.create_task(background_task())
        task3 = asyncio.create_task(start_streaming_monitoring())
        
        logger.info("All tasks created, starting concurrent execution")
        await asyncio.gather(task1, task2, task3)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        raise
