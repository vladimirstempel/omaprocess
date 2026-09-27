"""Reads /proc into Process values. The only module that knows /proc's layout."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .model import GroupKey, Pid, Process

_CMD_LIMIT = 200


@dataclass(frozen=True)
class _Stat:
    comm: str
    ppid: int
    cpu_ticks: int
    start_ticks: int


class ProcFs:
    def __init__(self, root: Path):
        self._root = root

    def scan(self, uid: int) -> list[Process]:
        pids = (Pid(int(entry.name)) for entry in self._root.iterdir() if entry.name.isdigit())
        processes = (self.read(pid) for pid in pids)
        return [p for p in processes if p is not None and p.uid == uid]

    def read(self, pid: Pid) -> Process | None:
        base = self._root / str(pid)
        try:
            status = (base / "status").read_text()
            stat = _parse_stat((base / "stat").read_text())
            argv = (base / "cmdline").read_bytes()
            cgroup = (base / "cgroup").read_text()
        except OSError:
            return None
        if not argv:
            return None
        return Process(pid=pid, ppid=stat.ppid, uid=_status_int(status, "Uid:"), comm=stat.comm,
                       exe=_readlink(base / "exe"), cmd=_command_line(argv),
                       rss=_status_int(status, "VmRSS:") * 1024, cpu_ticks=stat.cpu_ticks,
                       start_ticks=stat.start_ticks, group=GroupKey.for_cgroup(_unified(cgroup), pid))


def _parse_stat(text: str) -> _Stat:
    # comm may contain spaces and parentheses; it ends at the LAST ')'.
    open_at, close_at = text.index("("), text.rindex(")")
    rest = text[close_at + 2:].split()
    return _Stat(comm=text[open_at + 1:close_at], ppid=int(rest[1]),
                 cpu_ticks=int(rest[11]) + int(rest[12]), start_ticks=int(rest[19]))


def _status_int(status: str, label: str) -> int:
    for line in status.splitlines():
        if line.startswith(label):
            return int(line.split()[1])
    return 0


def _unified(cgroup: str) -> str:
    for line in cgroup.splitlines():
        if line.startswith("0::"):
            return line[3:]
    return ""


def _command_line(argv: bytes) -> str:
    parts = argv.rstrip(b"\0").split(b"\0")
    return " ".join(p.decode(errors="replace") for p in parts)[:_CMD_LIMIT]


def _readlink(path: Path) -> str:
    try:
        return os.readlink(path).removesuffix(" (deleted)")
    except OSError:
        return ""
