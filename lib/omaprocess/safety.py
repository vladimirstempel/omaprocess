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
        return (process.uid != self._uid or process.pid.value in self._untouchable
                or self._takes_down_session(process))

    def ensure_group_allowed(self, processes: Sequence[Process]) -> None:
        """Refuses when the group holds the shell or PID 1. The caller's own pids do not
        count: a terminal's scope holds the CLI and its shell, yet its other processes are fair game."""
        for process in processes:
            if self._takes_down_session(process):
                raise Refused(f"{process.comm} ({process.pid}) is protected: ending it would take down the shell")

    @staticmethod
    def _takes_down_session(process: Process) -> bool:
        return process.pid.value == 1 or process.comm in _SHELL_COMMANDS

    def ensure_allowed(self, processes: Sequence[Process]) -> None:
        for process in processes:
            self._ensure_one(process)

    def _ensure_one(self, process: Process) -> None:
        if process.uid != self._uid:
            raise Refused(f"{process.comm} ({process.pid}) belongs to another user")
        if self.is_protected(process):
            raise Refused(f"{process.comm} ({process.pid}) is protected: ending it would take down the shell")
