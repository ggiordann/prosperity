from __future__ import annotations

import time
from typing import Callable


def run_daemon(job: Callable[[], None], sleep_seconds: int) -> None:
    while True:
        job()
        time.sleep(sleep_seconds)
