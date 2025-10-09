from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import products, inspections, datasets
from inspections_watcher_task import inspections_watcher_task
from starlette.staticfiles import StaticFiles
import os
from app_config import APP_CONFIG
from services.my_logger import setup_logger

logger = setup_logger()

for folder in [APP_CONFIG["folder_inspection"]]:
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logger.info(f"フォルダを作成しました: {folder}")
        else:
            logger.debug(f"フォルダは既に存在します: {folder}")
    except Exception as e:
        logger.exception(f"フォルダ作成/確認時のエラー: {folder}: {e}")

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
