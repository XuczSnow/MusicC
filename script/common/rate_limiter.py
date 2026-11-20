# rate_limiter.py
# ✅ 统一API限流器：保证请求之间最小间隔 + 每N次请求额外喘息
import time
import threading


class RateLimiter:

    def __init__(
        self,
        min_interval=1.0,
        burst_count=100,
        burst_pause=10.0
    ):

        self.min_interval = min_interval
        self.burst_count = burst_count
        self.burst_pause = burst_pause

        self._lock = threading.Lock()
        self._last_ts = 0.0
        self._req_cnt = 0

    def wait(self):

        with self._lock:
            now = time.time()
            elapsed = now - self._last_ts

            delay = self.min_interval - elapsed
            if delay > 0:
                time.sleep(delay)

            self._req_cnt += 1
            self._last_ts = time.time()

            need_pause = (
                self.burst_count > 0
                and self._req_cnt % self.burst_count == 0
            )

        if need_pause:
            time.sleep(self.burst_pause)


# 预定义实例（各页面按需取用）
api_limiter = RateLimiter(min_interval=1.0, burst_count=100, burst_pause=10.0)
lyric_limiter = RateLimiter(min_interval=0.5, burst_count=200, burst_pause=15.0)
