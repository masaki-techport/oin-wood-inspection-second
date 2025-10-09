from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import products, inspections, datasets
from inspections_watcher_task import inspections_watcher_task
from starlette.staticfiles import StaticFiles
import os
from app_config import APP_CONFIG

if not os.path.exists(APP_CONFIG['upload_folder_dataset']):
    os.makedirs(APP_CONFIG['upload_folder_dataset'])
if not os.path.exists(APP_CONFIG['upload_folder_product']):
    os.makedirs(APP_CONFIG['upload_folder_product'])
if not os.path.exists(APP_CONFIG['upload_folder_inspection']):
    os.makedirs(APP_CONFIG['upload_folder_inspection'])

# create FastAPI Instance
app = FastAPI()
app.include_router(products.router)
app.include_router(inspections.router)
app.include_router(datasets.router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.mount("/data", StaticFiles(directory="data"), name="data")

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

        task1 = asyncio.create_task(start_fastapi())
        task2 = asyncio.create_task(background_task())
        await asyncio.gather(task1, task2)

    asyncio.run(main())
