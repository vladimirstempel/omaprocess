"""Turns a group of processes into the program's human name and icon."""
from __future__ import annotations

import re
from typing import Iterator, Protocol, Sequence

from .desktop import DesktopCatalog, DesktopEntry
from .model import Identity, Process
from .windows import WindowClasses

_WRAPPERS = frozenset({"bash", "sh", "zsh", "fish", "dash", "env", "uwsm", "systemd-run",
                       "gtk-launch", "xdg-terminal-exec"})
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def is_wrapper(process: Process) -> bool:
    return process.comm in _WRAPPERS or process.comm.startswith("srt-")


def _meaningful(processes: Sequence[Process]) -> list[Process]:
    return [p for p in processes if not is_wrapper(p)]


def _pretty_class(window_class: str) -> str:
    tail = window_class.rsplit(".", 1)[-1]
    return tail if _WORD.fullmatch(tail) else window_class


class NamingRule(Protocol):
    def identify(self, processes: Sequence[Process]) -> Identity | None: ...


class WindowClassRule:
    """A window names its program. Prefers the entry that launches this very executable,
    so a browser hosting a web-app window is still named after the browser."""

    def __init__(self, windows: WindowClasses, catalog: DesktopCatalog):
        self._windows = windows
        self._catalog = catalog

    def identify(self, processes: Sequence[Process]) -> Identity | None:
        fallback = None
        for process, window_class, entry in self._windows_of(processes):
            if entry and entry.executable in (process.exe_name, process.comm):
                return entry.identity()
            fallback = fallback or (entry.identity() if entry else Identity(_pretty_class(window_class)))
        return fallback

    def _windows_of(self, processes: Sequence[Process]) -> Iterator[tuple[Process, str, DesktopEntry | None]]:
        for process in processes:
            for window_class in self._windows.classes_for(process.pid):
                yield process, window_class, self._catalog.find_by_window_class(window_class)


class ExecutableRule:
    def __init__(self, catalog: DesktopCatalog):
        self._catalog = catalog

    def identify(self, processes: Sequence[Process]) -> Identity | None:
        for process in _meaningful(processes):
            entry = self._catalog.find_by_executable(process.exe_name) or self._catalog.find_by_executable(process.comm)
            if entry:
                return entry.identity()
        return None


class ProcessNameRule:
    def identify(self, processes: Sequence[Process]) -> Identity | None:
        candidates = _meaningful(processes) or list(processes)
        if not candidates:
            return None
        comm = candidates[0].comm
        return Identity(comm[:1].upper() + comm[1:])


class Namer:
    def __init__(self, rules: Sequence[NamingRule]):
        self._rules = rules

    def identify(self, processes: Sequence[Process]) -> Identity:
        oldest_first = sorted(processes, key=lambda p: (p.start_ticks, p.pid))
        for rule in self._rules:
            identity = rule.identify(oldest_first)
            if identity:
                return identity
        return Identity("Unknown")


def default_namer(catalog: DesktopCatalog, windows: WindowClasses) -> Namer:
    return Namer([WindowClassRule(windows, catalog), ExecutableRule(catalog), ProcessNameRule()])
