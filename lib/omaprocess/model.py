"""Domain values shared by every part of the helper. Depends on nothing."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum

_UNIT_NAME = re.compile(r"^[A-Za-z0-9:_.@\\-]+\.(scope|service)$")
_TERMINAL_SCOPE = re.compile(r"^[\w.-]+-\d+-\d+\.scope$")


class Refused(Exception):
    """An action the helper will not perform. The message is shown to the user."""


@dataclass(frozen=True, order=True)
class Pid:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int) or self.value <= 0:
            raise ValueError(f"invalid pid: {self.value!r}")

    @classmethod
    def parse(cls, text: str) -> Pid:
        if not text.isascii() or not text.isdigit() or int(text) == 0:
            raise Refused(f"not a process id: {text!r}")
        return cls(int(text))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class GroupKey:
    """Identifies one program: its systemd unit, or pid-<n> outside any unit."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or "/" in self.value:
            raise ValueError(f"invalid group key: {self.value!r}")

    @property
    def is_unit(self) -> bool:
        return bool(_UNIT_NAME.fullmatch(self.value))

    @classmethod
    def for_cgroup(cls, cgroup_path: str, pid: Pid) -> GroupKey:
        last = cgroup_path.rstrip("/").rsplit("/", 1)[-1]
        return cls(last or f"pid-{pid}")

    @classmethod
    def parse(cls, text: str) -> GroupKey:
        try:
            return cls(text)
        except ValueError as error:
            raise Refused(str(error)) from None

    def __str__(self) -> str:
        return self.value


class Section(Enum):
    APPS = "apps"
    SYSTEM = "system"

    @classmethod
    def of(cls, key: GroupKey) -> Section:
        name = key.value
        if name.startswith("app-dbus"):
            return cls.SYSTEM
        if name.startswith("app-") and name.endswith((".scope", ".service")):
            return cls.APPS
        if _TERMINAL_SCOPE.match(name):
            return cls.APPS
        return cls.SYSTEM


@dataclass(frozen=True)
class Process:
    pid: Pid
    ppid: int
    uid: int
    comm: str
    exe: str
    cmd: str
    rss: int
    cpu_ticks: int
    start_ticks: int
    group: GroupKey
    cpu: float = 0.0

    @property
    def exe_name(self) -> str:
        return self.exe.rsplit("/", 1)[-1]

    def with_cpu(self, cpu: float) -> Process:
        return replace(self, cpu=cpu)


@dataclass(frozen=True)
class Identity:
    name: str
    icon: str = ""


@dataclass(frozen=True)
class ProcessGroup:
    key: GroupKey
    identity: Identity
    processes: tuple[Process, ...]
    protected: bool

    @property
    def section(self) -> Section:
        return Section.of(self.key)

    @property
    def count(self) -> int:
        return len(self.processes)

    @property
    def rss(self) -> int:
        return sum(p.rss for p in self.processes)

    @property
    def cpu(self) -> float:
        return round(sum(p.cpu for p in self.processes), 1)
