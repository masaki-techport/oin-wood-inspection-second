import os
import datetime
import time
import logging
import inspect
from logging import StreamHandler, Formatter, DEBUG
from logging.handlers import TimedRotatingFileHandler
from app_config import APP_CONFIG


class SkipRepeatedFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.last_log = None

    def filter(self, record):
        current_log = (record.levelname, record.getMessage())
        if current_log == self.last_log:
            return False  # 重複メッセージをスキップ
        self.last_log = current_log
        return True


class TimeBasedFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, **kwargs):
        # 日付によるログファイル名: YYYY_MM_DD.log
        dir_name = os.path.dirname(filename)
        self.current_date = datetime.datetime.now().strftime("%Y_%m_%d")
        self.current_suffix = ""
        self.max_retries = 3
        self.retry_delay = 0.5
        self.rollover_times = {"": datetime.time(0, 0)}
        full_filename = os.path.join(
            dir_name, f"{datetime.datetime.now().strftime('%Y_%m_%d')}.log"
        )
        os.makedirs(os.path.dirname(full_filename), exist_ok=True)
        kwargs["delay"] = kwargs.get("delay", True)
        super().__init__(
            full_filename,
            when="midnight",
            backupCount=[APP_CONFIG["log_backup_count"]],
            encoding="utf-8",
            **kwargs,
        )
        self.baseFilename = full_filename
        self.stream = None

    def _close_stream(self):
        """適切なエラー処理で現在のストリームを安全に閉じる"""
        if self.stream:
            try:
                self.stream.flush()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
            finally:
                self.stream = None

    def _get_current_suffix(self):
        """現在の時間ベースのサフィックスを決定"""
        current_time = datetime.datetime.now().time()

        # 時間帯をソート
        sorted_times = sorted(self.rollover_times.items(), key=lambda x: x[1])

        # 深夜過ぎから最初の時間帯までは、前日の最後のサフィックスを使用
        if current_time < sorted_times[0][1]:
            prev_day = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
            self.current_date = prev_day
            return sorted_times[-1][0]

        # 適切な時間帯を見つける
        for i, (suffix, time_obj) in enumerate(sorted_times):
            if i < len(sorted_times) - 1:
                next_time = sorted_times[i + 1][1]
                if current_time >= time_obj and current_time < next_time:
                    return suffix
            else:
                if current_time >= time_obj:
                    return suffix

        # 一致が見つからない場合は最初のサフィックスをデフォルトとする
        return sorted_times[0][0]

    def _get_filename(self):
        """ファイル名を以下の形式で作成するだけです"""
        dir_name = os.path.dirname(self.baseFilename)
        filename = f"{self.current_date}.log"
        return os.path.join(dir_name, filename)

    def _open_with_retry(self):
        """ロックされているか使用中の場合は再試行してファイルを開く"""
        for attempt in range(self.max_retries):
            try:
                # 追加モードでファイルを開く
                stream = open(self.baseFilename, "a", encoding=self.encoding)
                return stream
            except (IOError, OSError) as e:
                if attempt < self.max_retries - 1:
                    # 再試行する前に少し待機
                    time.sleep(self.retry_delay * (attempt + 1))  # 指数バックオフ
                else:
                    # 最後の試行が失敗した場合は例外を発生
                    raise e
        return None

    def _ensure_stream_is_open(self):
        """適切な再試行ロジックでストリームが開いていることを確認"""
        if self.stream is None:
            try:
                # ディレクトリが存在することを確認
                os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)

                # ファイルを開く
                self.stream = self._open_with_retry()
                return True
            except Exception as e:
                print(f"Failed to open log file after {self.max_retries} attempts:{e}")
                return False
        return True

    def emit(self, record):
        """適切なファイルローテーションチェックでレコードを出力"""
        try:
            # ファイルを切り替える必要があるかチェック
            need_rollover = False

            # 日付が変更されたかチェック
            new_date = datetime.datetime.now().strftime("%Y%m%d")
            if new_date != self.current_date:
                self.current_date = new_date
                need_rollover = True

            # 時間帯が変更されたかチェック
            new_suffix = self._get_current_suffix()
            if new_suffix != self.current_suffix:
                self.current_suffix = new_suffix
                need_rollover = True

            # 必要に応じてロールオーバーを実行
            if need_rollover:
                self._close_stream()
                self.baseFilename = self._get_filename()

                # ディレクトリが存在することを確認
                os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)

                # 必要に応じて再オープンするためにストリームをNoneにリセット
                self.stream = None

            # ストリームが開いていることを確認
            if self._ensure_stream_is_open():
                try:
                    msg = self.format(record)
                    self.stream.write(msg + self.terminator)
                    self.flush()
                    self.close()
                except Exception as e:
                    # 書き込みが失敗した場合、ストリームを一度再オープン
                    print(f"Error writing to log: {e}")
                    self._close_stream()
                    if self._ensure_stream_is_open():
                        msg = self.format(record)
                        self.stream.write(msg + self.terminator)
                        self.flush()
            else:
                print("Stream is None, cannot emit log record.")
        except Exception as e:
            print(f"Unhandled error in emit: {e}")
            self.handleError(record)

    def doRollover(self):
        """新しいファイルへのロールオーバーを実行"""
        self._close_stream()
        self.current_date = datetime.datetime.now().strftime("%Y_%m_%d")
        self.current_suffix = self._get_current_suffix()
        self.baseFilename = self._get_filename()

        # ディレクトリが存在することを確認
        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)

        # 遅延を使用していない場合は、今すぐファイルを開く
        if not self.delay:
            try:
                self.stream = self._open_with_retry()
            except Exception as e:
                print(f"Error opening file during rollover: {e}")
                self.stream = None

    def flush(self):
        """ストリームが開いている場合はフラッシュ"""
        if self.stream:
            try:
                self.stream.flush()
            except Exception as e:
                print(f"Error flushing stream: {e}")

    def close(self):
        """ハンドラーを閉じてリソースを解放"""
        self._close_stream()
        super().close()


def close_logger_handlers(logger):
    """ロガーに関連付けられたすべてのハンドラーを閉じる"""
    if not logger:
        return

    handlers_to_remove = []

    for handler in logger.handlers:
        try:
            # 後で削除するためにハンドラーを保存
            handlers_to_remove.append(handler)

            # ハンドラーを適切に閉じる
            handler.flush()
            handler.close()
        except Exception as e:
            print(f"Error closing handler: {e}")

    # 閉じたハンドラーをロガーから削除
    for handler in handlers_to_remove:
        logger.removeHandler(handler)


# 各ワーカープロセスでロガーを設定
def setup_logger():
    # ログを出力したモジュールを取得する
    frame = inspect.stack()[1]
    module_name = inspect.getmodule(frame[0]).__name__
    file_name = os.path.basename(frame[1])
    logger_name = f"{file_name} - {module_name}"

    # ロガーを作成する
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 既存のハンドラーを削除して適切に閉じる
    close_logger_handlers(logger)

    if not logger.hasHandlers():
        # ハンドラーを追加
        add_logger_handler(logger)

    return logger


def add_logger_handler(logger):
    # Console handler
    sh = StreamHandler()
    sh.setLevel(DEBUG)
    sh.addFilter(SkipRepeatedFilter())
    formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    os.makedirs(APP_CONFIG["log_file_folder"], exist_ok=True)

    current_date = datetime.datetime.now().strftime("%Y_%m_%d")
    log_filename = os.path.join(APP_CONFIG["log_file_folder"], f"{current_date}.log")

    fh = None
    for retry in range(3):
        try:
            fh = TimeBasedFileHandler(
                filename=log_filename,
            )
            fh.setLevel(DEBUG)
            fh.addFilter(SkipRepeatedFilter())
            fh_formatter = Formatter(
                "%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s"
            )
            fh.setFormatter(fh_formatter)
            logger.addHandler(fh)
            break
        except Exception as e:
            print(f"Retry {retry + 1}/3: Error creating file handler: {e}")
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
            time.sleep(0.5)

    logger._file_handlers = [h for h in logger.handlers if isinstance(h, TimeBasedFileHandler)]
    return logger
