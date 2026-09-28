"""Which window classes each process owns, from Hyprland."""
from __future__ import annotations

import json
import subprocess
from typing import Protocol

from .model import Pid


class WindowClasses(Protocol):
    def classes_for(self, pid: Pid) -> tuple[str, ...]: ...


class NoWindows:
    def classes_for(self, pid: Pid) -> tuple[str, ...]:
        return ()


class HyprlandWindows:
    def __init__(self, clients_json: str):
        self._classes: dict[int, list[str]] = {}
        parsed = json.loads(clients_json)
        if not isinstance(parsed, list):
            raise ValueError("hyprctl clients: expected a list")
        for client in parsed:
            if not isinstance(client, dict):
                continue
            window_class = client.get("class") or client.get("initialClass")
            if window_class:
                try:
                    pid = int(client.get("pid", 0))
                    self._classes.setdefault(pid, []).append(window_class)
                except (TypeError, ValueError):
                    continue

    @classmethod
    def query(cls, run=subprocess.run) -> WindowClasses:
        try:
            result = run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2)
            return cls(result.stdout) if result.returncode == 0 else NoWindows()
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return NoWindows()

    def classes_for(self, pid: Pid) -> tuple[str, ...]:
        return tuple(self._classes.get(pid.value, ()))
