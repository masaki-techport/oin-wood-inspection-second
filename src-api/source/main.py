from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import inspection_status
from starlette.staticfiles import StaticFiles
import os
from app_config import APP_CONFIG, DB
from services.my_logger import setup_logger
from db.engine import initialize_database

logger = setup_logger()

# app_configからパスを取得して必要なディレクトリを作成
folders_to_create = [
    "data",  # 追加: StaticFiles用
    APP_CONFIG["folder_inspection"],  # 検査画像保存用
    os.path.dirname(DB["driver"].replace("sqlite:///", "")),  # DB用
    APP_CONFIG["log_file_folder"],  # ログ用
]

for folder in folders_to_create:
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
            logger.debug(f"フォルダを作成しました: {folder}")
        except Exception as e:
            logger.exception(f"フォルダ作成/確認時のエラー: {folder}: {e}")
    else:
        logger.debug(f"フォルダは既に存在します: {folder}")

try:
    initialize_database()
    logger.debug("データベースの初期化が完了しました")
except Exception as e:
    logger.exception(f"データベース初期化に失敗しました: {e}")

# create FastAPI Instance
app = FastAPI()
app.include_router(inspection_status.router)

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
        logger.info("アプリケーションが正常に開始しました")

        # バックエンドサーバーのタスク
        async def start_fastapi():
            config = uvicorn.Config(app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()

        await start_fastapi()

    asyncio.run(main())
