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
_ESCAPED = re.compile(r"\\x([0-9a-fA-F]{2})")
# What a unit is called after, in the order the shapes are tried.
_HYPRLAND_COMMAND = re.compile(r"app-Hyprland-(?P<hint>.+)-[0-9a-f]{8}\.scope")
_UNIT_HINTS = (
    _HYPRLAND_COMMAND,                                                  # a command Hyprland started
    re.compile(r"app-(?P<hint>.+?)(-\d+)?\.scope"),                     # app-<desktop id>-<pid>.scope
    re.compile(r"app-(?P<hint>.+?)(@[^@]*)?\.service"),                 # app-<desktop id>@autostart.service
    re.compile(r"dbus-:[\d.]+-(?P<hint>.+)@\d+\.service"),              # D-Bus activated
    re.compile(r".+@(?P<hint>.+)\.desktop\.service"),                   # wayland-wm@hyprland.desktop.service
    re.compile(r"(?P<hint>.+?)(@.*)?\.service"),
)


def is_wrapper(process: Process) -> bool:
    return process.comm in _WRAPPERS or process.comm.startswith("srt-")


def _meaningful(processes: Sequence[Process]) -> list[Process]:
    return [p for p in processes if not is_wrapper(p)]


def _title(name: str) -> str:
    """Capitalises a plain word. A compound name such as xdg-desktop-portal reads better as it is."""
    return name[:1].upper() + name[1:] if _WORD.fullmatch(name) else name


def _unescape(text: str) -> str:
    return _ESCAPED.sub(lambda m: chr(int(m.group(1), 16)), text)


def unit_hint(unit: str) -> str:
    """The desktop id, command or service a systemd unit is named after; "" when it has none."""
    for shape in _UNIT_HINTS:
        match = shape.fullmatch(unit)
        if match:
            return _unescape(match.group("hint"))
    return ""


def is_bare_command(unit: str) -> bool:
    """A command Hyprland started directly, such as an exec-once helper, not through an app launcher."""
    match = _HYPRLAND_COMMAND.fullmatch(unit)
    return match is not None and _unescape(match.group("hint")) not in _WRAPPERS


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
            fallback = fallback or (entry.identity() if entry
                                    else Identity(_pretty_class(window_class), recognised=True))
        return fallback

    def _windows_of(self, processes: Sequence[Process]) -> Iterator[tuple[Process, str, DesktopEntry | None]]:
        for process in processes:
            for window_class in self._windows.classes_for(process.pid):
                yield process, window_class, self._catalog.find_by_window_class(window_class)


class UnitEntryRule:
    """The launcher names the unit after the desktop entry, or the command, it started."""

    def __init__(self, catalog: DesktopCatalog):
        self._catalog = catalog

    def identify(self, processes: Sequence[Process]) -> Identity | None:
        hint = unit_hint(processes[0].group.value) if processes else ""
        if not hint or hint in _WRAPPERS:
            return None
        entry = self._catalog.find_by_id(hint) or self._catalog.find_by_executable(hint)
        return entry.identity() if entry else None


class ExecutableRule:
    def __init__(self, catalog: DesktopCatalog):
        self._catalog = catalog

    def identify(self, processes: Sequence[Process]) -> Identity | None:
        for process in _meaningful(processes):
            entry = self._catalog.find_by_executable(process.exe_name) or self._catalog.find_by_executable(process.comm)
            if entry:
                return entry.identity()
        return None


class UnitNameRule:
    """With no desktop entry, the unit's own name is what was started, and it is never cut short."""

    def identify(self, processes: Sequence[Process]) -> Identity | None:
        hint = unit_hint(processes[0].group.value) if processes else ""
        if not hint or hint in _WRAPPERS:
            return None
        return Identity(_title(_pretty_class(hint)))


class ProcessNameRule:
    def identify(self, processes: Sequence[Process]) -> Identity | None:
        candidates = _meaningful(processes) or list(processes)
        if not candidates:
            return None
        return Identity(_title(candidates[0].comm))


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
    # The unit rules come before the executable: a terminal or an agent session holds many
    # unrelated programs, and a desktop entry of one of them is not what the user started.
    return Namer([WindowClassRule(windows, catalog), UnitEntryRule(catalog), UnitNameRule(),
                  ExecutableRule(catalog), ProcessNameRule()])
