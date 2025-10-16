import pytz
from fastapi import APIRouter
from modules.sensor.src import sensor_monitor
from services.my_logger import setup_logger

router = APIRouter(prefix="/inspection_status")
jp_timezone = pytz.timezone("Asia/Tokyo")

logger = setup_logger()

# 最新のセンサ状態を保存する変数
latest_status = {
    "a_sensor": None,
    "b_sensor": None,
    "wood_move_result": None,
    "wood_move_state": None,
}


@router.get(
    "/latest",
    description="最新の検査ステータスを取得",
)
def responce_latest_status():
    try:
        latest_status = sensor_monitor.get_latest_status()
        return latest_status
    except Exception:
        logger.exception("最新の検査ステータス取得時にエラー")
        return {"result": False, "message": "最新の検査ステータス取得時にエラー"}
