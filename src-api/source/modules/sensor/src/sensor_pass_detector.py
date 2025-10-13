import threading
from time import sleep, time
from modules.sensor.src import Input_Monitoring


# センサ通過判定用ステートマシン
class SensorStateMachine:
    TIMEOUT_SEC = 30.0  # 動作判定タイムアウト（秒）

    def __init__(self, on_decision=None):
        # 初期状態はIDLE（待機）
        self.state = "IDLE"
        self.last_event_time = time()  # 最後のイベント発生時刻
        self.sequence = []  # イベント履歴
        self.result = None  # 判定結果
        self.on_decision = on_decision  # 判定時に呼ばれるコールバック

    def reset(self):
        if self.result is not None and self.on_decision:
            self.on_decision(self.result, self.state)  # ← stateも渡す
        # ステートマシンを初期状態に戻す
        self.state = "IDLE"
        self.last_event_time = time()
        self.sequence = []
        self.result = None
        print("--------------------")

    def on_event(self, event):
        now = time()
        # タイムアウト判定：一定時間イベントがなければエラー
        if now - self.last_event_time > self.TIMEOUT_SEC:
            self.result = "error"
            self.reset()
            return "error"

        self.last_event_time = now
        self.sequence.append(event)

        # 状態遷移ロジック
        if self.state == "IDLE":
            if event == "A_ON":
                self.state = "A_ACTIVE"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
            elif event == "B_ON":
                self.state = "B_ACTIVE"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
        elif self.state == "A_ACTIVE":
            if event == "B_ON":
                self.state = "A_THEN_B"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
            elif event == "A_OFF":
                self.result = "return_from_R"
                self.reset()
                return "return_from_R"
            elif event == "B_OFF":
                self.result = "error"
                self.reset()
                return "error"
        elif self.state == "B_ACTIVE":
            if event == "A_ON":
                self.state = "B_THEN_A"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
            elif event == "B_OFF":
                self.result = "return_from_L"
                self.reset()
                return "return_from_L"
            elif event == "A_OFF":
                self.result = "error"
                self.reset()
                return "error"
        elif self.state == "A_THEN_B":
            if event == "A_OFF":
                self.state = "B_ONLY"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
            elif event == "B_OFF":
                self.state = "A_ONLY_return"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
        elif self.state == "B_THEN_A":
            if event == "B_OFF":
                self.state = "A_ONLY"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
            elif event == "A_OFF":
                self.state = "B_ONLY_return"
                if self.on_decision:
                    self.on_decision(None, self.state)  # 状態遷移時コールバック
        elif self.state == "A_ONLY":
            if event == "A_OFF":
                self.result = "pass_L_to_R"
                self.reset()
                return "pass_L_to_R"
            elif event == "B_ON":
                self.result = "return_from_L"
                self.reset()
                return "return_from_L"
        elif self.state == "B_ONLY":
            if event == "B_OFF":
                self.result = "pass_R_to_L"
                self.reset()
                return "pass_R_to_L"
            elif event == "A_ON":
                self.result = "return_from_R"
                self.reset()
                return "return_from_R"
        elif self.state == "A_ONLY_return":
            if event == "A_OFF":
                self.result = "return_from_R"
                self.reset()
                return "return_from_R"
            elif event == "B_ON":
                self.result = "error"
                self.reset()
                return "error"
        elif self.state == "B_ONLY_return":
            if event == "B_OFF":
                self.result = "return_from_L"
                self.reset()
                return "return_from_L"
            elif event == "A_ON":
                self.result = "error"
                self.reset()
                return "error"

        # どの状態でも、両方OFFならIDLEに戻す
        if self.state != "IDLE":
            if len(self.sequence) >= 2:
                if (
                    self.sequence[-1] in ["A_OFF", "B_OFF"]
                    and self.sequence[-2] in ["A_OFF", "B_OFF"]
                    and self.sequence[-1] != self.sequence[-2]
                ):
                    self.result = "timeout_or_manual_reset"
                    self.reset()
                    return "timeout_or_manual_reset"

        # イベント履歴が多すぎる場合はエラー
        if len(self.sequence) > 5:
            self.result = "error"
            self.reset()
            return "error"

        return None


# 最新のセンサ値を保存するグローバル変数
latest_sensor_values = {
    "A": None,
    "B": None,
}


# センサA（ビット0）、センサB（ビット1）の状態変化を監視し、イベントをステートマシンに渡す関数
def sensor_event_monitor(on_decision=None, interval_sec=0.02):
    """
    センサA（ビット0）、センサB（ビット1）の状態変化を監視し、イベントをステートマシンに渡す
    """
    sm = SensorStateMachine(on_decision=on_decision)
    prev_A = Input_Monitoring.watch_specific_bit_once(0)
    prev_B = Input_Monitoring.watch_specific_bit_once(1)

    # 初期値を保存
    latest_sensor_values["A"] = prev_A
    latest_sensor_values["B"] = prev_B

    while True:
        curr_A = Input_Monitoring.watch_specific_bit_once(0)
        curr_B = Input_Monitoring.watch_specific_bit_once(1)

        # 最新値を保存
        latest_sensor_values["A"] = curr_A
        latest_sensor_values["B"] = curr_B

        # センサAの変化を検出
        if curr_A != prev_A:
            event = "A_ON" if curr_A else "A_OFF"
            sm.on_event(event)
            # print(f"Event: {event}, State: {sm.state}, Result: {result}")
            prev_A = curr_A

        # センサBの変化を検出
        if curr_B != prev_B:
            event = "B_ON" if curr_B else "B_OFF"
            sm.on_event(event)
            # print(f"Event: {event}, State: {sm.state}, Result: {result}")
            prev_B = curr_B

        sleep(interval_sec)


# モジュールとして使う場合の例
def start_sensor_monitor(on_decision, interval_sec=0.02):
    Input_Monitoring.Initialization()
    t = threading.Thread(
        target=sensor_event_monitor, args=(on_decision, interval_sec), daemon=True
    )
    t.start()
    return t


# 直接実行時は従来通り
if __name__ == "__main__":

    def print_decision(result, state):
        print(f"Result: {result}, State: {state}")

    Input_Monitoring.Initialization()
    print("--------------------")
    t = threading.Thread(target=sensor_event_monitor, args=(print_decision,), daemon=True)
    t.start()
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("終了します。")
