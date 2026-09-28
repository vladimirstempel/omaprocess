"""Finds the human name and icon of a program from its .desktop entry."""
from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .model import Identity


@dataclass(frozen=True)
class DesktopEntry:
    id: str
    name: str
    icon: str
    executable: str
    wm_class: str

    def identity(self) -> Identity:
        return Identity(self.name, self.icon)


def parse_desktop_file(path: Path) -> DesktopEntry | None:
    fields = _main_section(path.read_text(errors="replace"))
    if fields.get("Hidden", "").lower() == "true" or not fields.get("Name"):
        return None
    return DesktopEntry(id=path.stem, name=fields["Name"], icon=fields.get("Icon", ""),
                        executable=_executable(fields.get("Exec", "")),
                        wm_class=fields.get("StartupWMClass", ""))


def _main_section(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    inside = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            fields.setdefault(key.strip(), value.strip())
    return fields


def _executable(exec_line: str) -> str:
    try:
        tokens = shlex.split(exec_line)
    except ValueError:
        tokens = exec_line.split()
    if tokens and tokens[0] == "env":
        tokens = tokens[1:]
    program = next((t for t in tokens if "=" not in t), "")
    return program.rsplit("/", 1)[-1]


class DesktopCatalog:
    def __init__(self, entries: Iterable[DesktopEntry]):
        self._by_wm_class: dict[str, DesktopEntry] = {}
        self._by_id: dict[str, DesktopEntry] = {}
        self._by_id_tail: dict[str, DesktopEntry] = {}
        self._by_executable: dict[str, DesktopEntry] = {}
        for entry in entries:
            self._index(entry)

    @classmethod
    def load(cls, dirs: Sequence[Path]) -> DesktopCatalog:
        seen: set[str] = set()
        entries: list[DesktopEntry] = []
        for path in (p for d in dirs if d.is_dir() for p in sorted(d.rglob("*.desktop"))):
            if path.stem in seen:
                continue
            seen.add(path.stem)
            entry = _parse_quietly(path)
            if entry:
                entries.append(entry)
        return cls(entries)

    def find_by_window_class(self, window_class: str) -> DesktopEntry | None:
        key = window_class.lower()
        return self._by_wm_class.get(key) or self._by_id.get(key) or self._by_id_tail.get(key)

    def find_by_executable(self, name: str) -> DesktopEntry | None:
        return self._by_executable.get(name.lower()) if name else None

    def _index(self, entry: DesktopEntry) -> None:
        if entry.wm_class:
            self._by_wm_class.setdefault(entry.wm_class.lower(), entry)
        self._by_id.setdefault(entry.id.lower(), entry)
        self._by_id_tail.setdefault(entry.id.rsplit(".", 1)[-1].lower(), entry)
        executable = entry.executable.lower()
        if executable and (executable not in self._by_executable or entry.id.lower() == executable):
            self._by_executable[executable] = entry


def _parse_quietly(path: Path) -> DesktopEntry | None:
    try:
        return parse_desktop_file(path)
    except OSError:
        return None
