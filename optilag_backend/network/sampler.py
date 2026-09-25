"""Amostragem contínua em background para o motor OptiLag."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque, Optional

from .probes import ProbeResult, multi_probe


class ProbeSampler:
    def __init__(self, interval: float = 5.0, history: int = 60, on_result: Optional[Callable[[ProbeResult], None]] = None):
        self.interval = interval
        self.history: Deque[ProbeResult] = deque(maxlen=history)
        self.on_result = on_result
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last: Optional[ProbeResult] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="OptiLagProbeSampler")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                result = multi_probe()
                self.last = result
                self.history.append(result)
                if self.on_result:
                    self.on_result(result)
            except Exception:
                pass
            self._stop.wait(self.interval)

    def series_combined(self) -> list:
        return [r.combined for r in self.history if r.combined is not None]

    def series_udp(self) -> list:
        return [r.udp for r in self.history if r.udp is not None]
