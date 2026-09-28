"""What the helper will never signal. Enforced here, not only hidden in the UI."""
from __future__ import annotations

from typing import Sequence

from .model import Process, Refused

_SHELL_COMMANDS = frozenset({"quickshell", "qs", "omarchy-shell"})


class ProtectionPolicy:
    def __init__(self, uid: int, untouchable: frozenset[int]):
        self._uid = uid
        self._untouchable = untouchable

    def is_protected(self, process: Process) -> bool:
        return (process.uid != self._uid or process.pid.value == 1
                or process.pid.value in self._untouchable or process.comm in _SHELL_COMMANDS)

    def ensure_allowed(self, processes: Sequence[Process]) -> None:
        if not processes:
            raise Refused("no such program or process is running")
        for process in processes:
            self._ensure_one(process)

    def _ensure_one(self, process: Process) -> None:
        if process.uid != self._uid:
            raise Refused(f"{process.comm} ({process.pid}) belongs to another user")
        if self.is_protected(process):
            raise Refused(f"{process.comm} ({process.pid}) is protected: ending it would take down the shell")
