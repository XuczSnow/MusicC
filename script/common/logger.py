import os
import logging
import traceback
import queue
import time

from logging.handlers import RotatingFileHandler
from datetime import datetime


class AppLogger:

    def __init__(
        self,
        textbox=None,
        log_dir="logs",
        max_mb=10,
        backup_count=5
    ):

        self.textbox = textbox

        self.queue = queue.Queue()

        self.cache_hit_count = 0
        self.cache_miss_count = 0

        os.makedirs(
            log_dir,
            exist_ok=True
        )

        self.logger = logging.getLogger(
            "MusicApp"
        )

        self.logger.setLevel(
            logging.DEBUG
        )

        self.logger.handlers.clear()
        
        self.log_path = log_dir

        log_file = os.path.join(
            log_dir,
            f"{datetime.now().strftime("%Y-%m-%d")}.log"
        )

        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8"
        )

        formatter = logging.Formatter(
            "[%(asctime)s] "
            "[%(levelname)s] "
            "%(message)s",
            datefmt="%H:%M:%S"
        )

        handler.setFormatter(
            formatter
        )

        self.logger.addHandler(
            handler
        )

        console = logging.StreamHandler()

        console.setFormatter(
            formatter
        )

        self.logger.addHandler(
            console
        )

        if self.textbox:

            self.start_gui_updater()
            
        self.clean_old_logs(keep_days=30)

    # =========================
    # 清除旧日志
    # =========================
    def clean_old_logs(self, keep_days=30):

        now = time.time()

        expire_seconds = (
            keep_days
            * 24
            * 3600
        )

        for file in os.listdir(self.log_path):

            path = os.path.join(
                self.log_path,
                file
            )

            if not os.path.isfile(path):
                continue

            age = now - os.path.getmtime(path)

            if age > expire_seconds:

                try:

                    os.remove(path)

                    print(
                        "删除:",
                        path
                    )

                except Exception as e:

                    print(e)

    # =========================
    # GUI
    # =========================

    def start_gui_updater(self):

        def process():

            try:

                while True:

                    level, msg = (
                        self.queue.get_nowait()
                    )

                    self.write_gui(
                        level,
                        msg
                    )

            except queue.Empty:
                pass

            if (
                self.textbox
                and
                self.textbox.winfo_exists()
            ):

                self.textbox.after(
                    100,
                    process
                )

        process()

    def write_gui(
        self,
        level,
        msg
    ):

        if not self.textbox:
            return

        icons = {

            "INFO": "✅",

            "WARNING": "⚠️",

            "ERROR": "❌",

            "CRITICAL": "🔥",

            "DEBUG": "🔍"
        }

        icon = icons.get(
            level,
            ""
        )

        text = (
            f"{icon} "
            f"{msg}\n"
        )

        try:

            self.textbox.insert(
                "end",
                text
            )

            self.textbox.see(
                "end"
            )

        except:
            pass

    # =========================
    # 内部统一入口
    # =========================

    def _log(
        self,
        level,
        msg
    ):

        getattr(
            self.logger,
            level.lower()
        )(msg)

        self.queue.put(
            (
                level,
                msg
            )
        )

    # =========================
    # 常用等级
    # =========================

    def debug(
        self,
        msg
    ):
        self._log(
            "DEBUG",
            msg
        )

    def info(
        self,
        msg
    ):
        self._log(
            "INFO",
            msg
        )

    def warning(
        self,
        msg
    ):
        self._log(
            "WARNING",
            msg
        )

    def error(
        self,
        msg
    ):
        self._log(
            "ERROR",
            msg
        )

    def critical(
        self,
        msg
    ):
        self._log(
            "CRITICAL",
            msg
        )

    # =========================
    # 异常
    # =========================

    def exception(
        self,
        exc
    ):

        text = (
            f"{str(exc)}\n\n"
            + traceback.format_exc()
        )

        self.critical(
            text
        )

    # =========================
    # 缓存统计
    # =========================

    def cache_hit(self):

        self.cache_hit_count += 1

    def cache_miss(self):

        self.cache_miss_count += 1

    def cache_report(self):

        total = (
            self.cache_hit_count
            +
            self.cache_miss_count
        )

        if total == 0:

            hit_rate = 0

        else:

            hit_rate = (
                self.cache_hit_count
                / total
                * 100
            )

        self.info(
            f"缓存命中率: "
            f"{hit_rate:.2f}% "
            f"(Hit={self.cache_hit_count}, "
            f"Miss={self.cache_miss_count})"
        )

    # =========================
    # 指标统计
    # =========================

    def metric(
        self,
        name,
        value
    ):

        self.info(
            f"[METRIC] "
            f"{name}={value}"
        )

    # =========================
    # 启动信息
    # =========================

    def startup_info(self):

        self.info(
            "AI Music Classifier 启动"
        )

        self.info(
            f"启动时间: "
            f"{datetime.now()}"
        )

    # =========================
    # 导出日志
    # =========================

    def export(self):

        self.info(
            "日志导出完成"
        )