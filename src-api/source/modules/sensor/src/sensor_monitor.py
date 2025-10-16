from modules.sensor.src import sensor_pass_detector
import threading
from services.my_logger import setup_logger

logger = setup_logger()

# 最新のセンサ状態を保存する変数
latest_status = {
    "a_sensor": None,  # Aセンサの状態
    "b_sensor": None,  # Bセンサの状態
    "wood_move_result": None,  # 木材の移動結果
    "wood_move_state": None,  # 木材の移動状態
}


def on_sensor_event(result, state):
    # センサ値に変化があったらlatest_statusを更新
    latest_status["wood_move_result"] = result
    latest_status["wood_move_state"] = state

    # 状態に応じてログを出力
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


# センサ監視の排他制御用ロック
sensor_monitor_lock = threading.Lock()
# センサ監視が開始されているかどうかのフラグ
sensor_monitor_started = False


def start_sensor_monitor():
    """
    センサ監視を開始する関数。
    既に監視が開始されていなければ、sensor_pass_detectorの監視を開始する。
    """
    try:
        logger.info("センサの監視を開始")
        global sensor_monitor_started
        with sensor_monitor_lock:
            if not sensor_monitor_started:
                sensor_pass_detector.start_sensor_monitor(on_sensor_event)
                sensor_monitor_started = True
        logger.info("センサの監視を開始")
        return {"result": True, "message": "センサの監視を開始"}
    except Exception as ex:
        logger.exception(f"センサの監視を開始時にエラー: {ex}")
        return {"result": False, "message": f"Failed!! {ex}"}


def get_latest_status():
    """
    最新のセンサ値を取得し、latest_statusに反映して返す関数。
    """
    with sensor_monitor_lock:
        latest_status["a_sensor"] = sensor_pass_detector.latest_sensor_values["A"]
        latest_status["b_sensor"] = sensor_pass_detector.latest_sensor_values["B"]
        # コピーを返すことで呼び出し元での変更を防ぐ
        return latest_status.copy()
