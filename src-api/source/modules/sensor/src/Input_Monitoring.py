# ================================================================
# ================================================================
# API-DIO(WDM)
# 入出力デモ
# 入力があった際、対応する出力を返すコード（ループ処理切れない）
# ================================================================
# ================================================================

# CONTEC共有ライブラリ内の関数の呼び出しを行うためには、外部関数ライブラリモジュール(ctypes)が必要のためimportする
# CONTEC共有ライブラリではWindows固有の型を使用いるため、ctypes.wintypesも合わせてimportする
import ctypes
import sys
import os
from time import sleep
import threading
import yaml
from modules.sensor.src import cdio

# PythonでAPI-DIO(WDM)の関数を使用するにはcdio.pyファイルが必要となります。
# 作成するプログラムの入ったフォルダーに、API-DIO(WDM)の定義モジュール (DIOWDM/sample/Inc/cdio.py)をコピーしてください。
# ソースコード中でAPI-DIO(WDM)の定義モジュールをimportしてください。

# ================================================================
# 固定変数定義
# ================================================================
default_name = "DIO001"  # Ethernet接続のデバイス名デフォルト値

# ================================================================
# 設定ファイルの読み込み
# ================================================================
# 設定ファイル
config_file = os.path.join(os.path.dirname(__file__), "..", "config", "DIO_setting.yaml")
config_file = os.path.abspath(config_file)
# パラメータファイル読みこみ
with open(file=config_file, mode="r", encoding="utf-8") as file:
    DIO_params = yaml.safe_load(file)

dev_name_params = DIO_params.get("dev_name", default_name)

# ----------------------------------------
# ctypesライブラリを使ってC言語のデータ型と互換性のあるPythonのデータ型を定義
# ----------------------------------------
dio_id = ctypes.c_short()
io_data = ctypes.c_ubyte()
port_no = ctypes.c_short()
bit_no = ctypes.c_short()
err_str = ctypes.create_string_buffer(256)


# ================================================================
# 文字列を数値に変換できるかどうか確認する関数
# ================================================================
def isnum(str, base):
    try:
        if 16 == base:
            int(str, 16)
        else:
            int(str)
    except Exception:
        return False
    return True


# ----------------------------------------
# ドライバ初期化処理（デフォルト値のみ使用）
# ----------------------------------------
def Initialization():
    # dev_name_paramsが不適ならdefault_nameを使う
    dev_name = dev_name_params
    if not isinstance(dev_name, str) or not dev_name.strip():
        print("設定ファイルのDIO_paramsが不適切です。デフォルト値を使用します。")
        dev_name = default_name
    print(f"dev_name : {dev_name}")
    lret = cdio.DioInit(dev_name.encode(), ctypes.byref(dio_id))
    if lret != cdio.DIO_ERR_SUCCESS:
        dev_name = default_name
        print(f"DioInit失敗: 再度デフォルト値 {dev_name} で接続を試みます。")
        lret = cdio.DioInit(dev_name.encode(), ctypes.byref(dio_id))
        if lret != cdio.DIO_ERR_SUCCESS:
            cdio.DioGetErrorString(lret, err_str)
            print(f"DioInit = {lret}: {err_str.value.decode('sjis')}")
            print("DIOの接続を確認してください。")
            print("終了します。")
            sys.exit()
    print(f"dev_name : {dev_name} で初期化成功")


Initialization()
print("Initialization execution OK")


# ================================================================
# 指定したビット番号の入力状態を1回だけ取得する関数
# ================================================================
def watch_specific_bit_once(target_bit_no):
    """
    指定したビット番号の入力状態を1回だけ取得し、True/Falseで返す
    """
    bit_no = ctypes.c_short(int(target_bit_no))
    lret = cdio.DioInpBit(dio_id, bit_no, ctypes.byref(io_data))
    if lret == cdio.DIO_ERR_SUCCESS:
        current_state = io_data.value
        # print(f'DioInpBit bit = {bit_no.value}: data = 0x{current_state:02x}')
        return bool(current_state)
    else:
        cdio.DioGetErrorString(lret, err_str)
        print(f"DioInpBit = {lret}: {err_str.value.decode('sjis')}")
        return None


# ================================================================
# 指定したビット番号の入力状態を定期的に取得する関数（動作確認用ループ）
# ================================================================
def watch_specific_bit_loop(target_bit_no, interval_sec):
    """
    指定したビット番号の入力状態を定期的に取得して表示
    """
    while True:
        state = watch_specific_bit_once(target_bit_no)
        print(f"bit {target_bit_no} state: {state}")
        sleep(interval_sec)


# ----------------------------------------
# main関数呼び出し
# ----------------------------------------
# 他のモジュールにインポートされたときに、main() 関数を実行しないようにするために非常に一般的に使われます。
if __name__ == "__main__":
    interval_sec = 0.01  # 監視間隔（秒）

    # ビット0の監視スレッド
    t0 = threading.Thread(target=watch_specific_bit_loop, args=(0, interval_sec), daemon=True)
    t0.start()

    # ビット1の監視スレッド
    t1 = threading.Thread(target=watch_specific_bit_loop, args=(1, interval_sec), daemon=True)
    t1.start()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("終了します。")
