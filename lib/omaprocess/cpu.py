"""CPU % needs two samples; the previous one is kept in a small state file."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Sequence

from .model import Process


class CpuSampler:
    def __init__(self, state_file: Path, clock=time.monotonic,
                 ticks_per_second: int = os.sysconf("SC_CLK_TCK")):
        self._state_file = state_file
        self._clock = clock
        self._hz = ticks_per_second

    def apply(self, processes: Sequence[Process]) -> list[Process]:
        now = self._clock()
        previous = self._load()
        elapsed = now - previous.get("time", now)
        before = previous.get("procs", {})
        sampled = [p.with_cpu(self._usage(p, before.get(str(p.pid)), elapsed)) for p in processes]
        self._save(now, processes)
        return sampled

    def _usage(self, process: Process, before: list[int] | None, elapsed: float) -> float:
        if not before or elapsed <= 0 or before[1] != process.start_ticks:
            return 0.0
        ticks = max(0, process.cpu_ticks - before[0])
        return round(ticks / self._hz / elapsed * 100, 1)

    def _load(self) -> dict:
        try:
            state = json.loads(self._state_file.read_text())
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, now: float, processes: Sequence[Process]) -> None:
        state = {"time": now, "procs": {str(p.pid): [p.cpu_ticks, p.start_ticks] for p in processes}}
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_file.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state))
        os.replace(temporary, self._state_file)
