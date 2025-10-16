from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import inspection_status
from starlette.staticfiles import StaticFiles
import os
from app_config import APP_CONFIG, DB
from services.my_logger import setup_logger
from db.engine import initialize_database
from modules.sensor.src import sensor_monitor
import urllib

logger = setup_logger()

# 必要なディレクトリを作成（検査画像、DB、ログ、静的ファイル用）
db_url = DB["driver"]
if db_url.startswith("sqlite:///"):
    db_path = urllib.parse.urlparse(db_url).path.lstrip("/")
    db_dir = os.path.dirname(db_path)
else:
    db_dir = ""

folders_to_create = [
    "data",
    APP_CONFIG["folder_inspection"],
    db_dir,
    APP_CONFIG["log_file_folder"],
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
    # データベース初期化
    initialize_database()
    logger.debug("データベースの初期化が完了しました")
except Exception as e:
    logger.exception(f"データベース初期化に失敗しました: {e}")

# FastAPIアプリケーションのインスタンス作成
app = FastAPI()
# ルーターを追加（APIエンドポイントの登録）
app.include_router(inspection_status.router)

# CORS設定（全てのオリジン・メソッド・ヘッダーを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

# /data パスで静的ファイルを公開
app.mount("/data", StaticFiles(directory="data"), name="data")

if __name__ == "__main__":
    import uvicorn
    import asyncio

    async def main():
        # センサ監視を開始
        sensor_monitor.start_sensor_monitor()
        logger.info("アプリケーションが正常に開始しました")

        # FastAPIサーバーを起動
        async def start_fastapi():
            config = uvicorn.Config(app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()

        await start_fastapi()

    asyncio.run(main())
