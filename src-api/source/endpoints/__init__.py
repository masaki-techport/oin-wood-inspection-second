from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from endpoints.inspections import router as inspections_router
from endpoints.inference import router as inference_router
from endpoints.camera import router as camera_router
from endpoints.webcam_camera import router as webcam_router
from endpoints.sensor_inspection import router as sensor_inspection_router
from endpoints.file_api import router as file_api_router

def setup_routers(app: FastAPI):
    api_router = APIRouter()
    api_router.include_router(inspections_router)
    api_router.include_router(inference_router)
    api_router.include_router(camera_router)
    api_router.include_router(webcam_router)
    api_router.include_router(direction_router)
    api_router.include_router(sensor_inspection_router)
    api_router.include_router(file_api_router)
    
    app.include_router(api_router)

def setup_middlewares(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
