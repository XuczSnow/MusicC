# cache_manager.py

import json
import os
import time


class JsonCache:

    def __init__(
        self,
        cache_file,
        expire_days=30
    ):

        self.cache_file = cache_file

        self.expire_seconds = (
            expire_days * 24 * 3600
        )

        self.cache = {}

        self.load()

    def load(self):

        if os.path.exists(
            self.cache_file
        ):

            try:

                with open(
                    self.cache_file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    self.cache = json.load(f)

            except:

                self.cache = {}

    def save(self):

        os.makedirs(
            os.path.dirname(
                self.cache_file
            ),
            exist_ok=True
        )

        with open(
            self.cache_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.cache,
                f,
                ensure_ascii=False,
                indent=2
            )

    def get(
        self,
        key
    ):

        item = self.cache.get(key)

        if not item:

            return None

        age = (
            time.time()
            - item["timestamp"]
        )

        if age > self.expire_seconds:

            return None

        return item["data"]

    def set(
        self,
        key,
        data
    ):

        self.cache[key] = {

            "timestamp":
            time.time(),

            "data":
            data
        }
