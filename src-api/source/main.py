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

if not os.path.exists(APP_CONFIG['upload_folder_inspection']):
    os.makedirs(APP_CONFIG['upload_folder_inspection'])

#create database tables
initialize_database()

# create FastAPI Instance
app = FastAPI()

# Add a simple health check endpoint for network testing
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running and accessible"}

@app.get("/api/health")
async def api_health_check():
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.mount("/data", StaticFiles(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")), name="data")

if __name__ == "__main__":
    import uvicorn
    import asyncio

    async def main():
        # バックエンドサーバーのタスク
        async def start_fastapi():
            config = uvicorn.Config(app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()

        # 他のタスク
        async def background_task():
            await inspections_watcher_task()
        
        # Start streaming monitoring services
        async def start_streaming_monitoring():
            try:
                from streaming.monitoring import start_monitoring
                await start_monitoring()
            except Exception as e:
                print(f"[WARNING] Failed to start streaming monitoring: {e}")

        task1 = asyncio.create_task(start_fastapi())
        task2 = asyncio.create_task(background_task())
        task3 = asyncio.create_task(start_streaming_monitoring())
        await asyncio.gather(task1, task2, task3)

    asyncio.run(main())
