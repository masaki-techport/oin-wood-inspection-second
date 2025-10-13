import pytz
from fastapi import APIRouter, BackgroundTasks
from modules.sensor.src import sensor_pass_detector
import threading
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


def on_sensor_event(result, state):
    # センサ値に変化があったらlatest_statusを更新
    latest_status["wood_move_result"] = result
    latest_status["wood_move_state"] = state

    if result == "pass_L_to_R":
        logger.debug(f"【Save】左→右通過時の処理（Result: {result}, State: {state}）")
    elif state == "IDLE":
        logger.debug(f"【Idle】待機中（Result: {result}, State: {state}）")
    elif result == "return_from_L":
        logger.debug(f"【Delete】左から折返し（Result: {result}, State: {state})")
    elif result == "error":
        logger.debug(f"【Delete】エラー判定（Result: {result}, State: {state}）")
    elif state == "B_ACTIVE":
        logger.debug(f"【Rec】B側センサON (Result: {result}, State: {state})")


sensor_monitor_lock = threading.Lock()
sensor_monitor_started = False


def start_sensor_monitor_once():
    global sensor_monitor_started
    with sensor_monitor_lock:
        if not sensor_monitor_started:
            sensor_pass_detector.start_sensor_monitor(on_sensor_event)
            sensor_monitor_started = True


@router.get(
    "",
    description="検査の進行状況や状態を取得（監視開始）",
)
def get_inspection_status(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(start_sensor_monitor_once)
        logger.info("センサの監視を開始")
        return {"result": True, "message": "センサの監視を開始"}
    except Exception as ex:
        logger.exception(f"センサの監視を開始時にエラー: {ex}")
        return {"result": False, "message": f"Failed!! {ex}"}


@router.get(
    "/latest",
    description="最新のセンサ状態を取得",
)
def get_latest_status():
    latest_status["a_sensor"] = sensor_pass_detector.latest_sensor_values["A"]
    latest_status["b_sensor"] = sensor_pass_detector.latest_sensor_values["B"]
    return latest_status
