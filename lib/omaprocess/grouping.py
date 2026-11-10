"""Collects processes into programs. A program starts as one cgroup unit, then takes in
the units that belong to it: those its processes started, and those with its name."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from .model import GroupKey, Identity, Process, ProcessGroup, Section
from .naming import Namer, is_bare_command
from .safety import ProtectionPolicy


@dataclass(frozen=True)
class _Unit:
    key: GroupKey
    processes: tuple[Process, ...]
    identity: Identity

    @property
    def started(self) -> tuple[int, int]:
        return min((p.start_ticks, p.pid.value) for p in self.processes)

    @property
    def app_like(self) -> bool:
        return self.identity.windowed or Section.of(self.key) is Section.APPS


def group_processes(processes: Sequence[Process], namer: Namer, policy: ProtectionPolicy) -> list[ProcessGroup]:
    members: dict[GroupKey, list[Process]] = defaultdict(list)
    for process in processes:
        members[process.group].append(process)
    units = sorted((_Unit(key, tuple(found), namer.identify(found)) for key, found in members.items()),
                   key=lambda unit: unit.started)
    programs = _Programs(units)
    programs.join_started_units(processes)
    programs.join_same_identity()
    groups = [_group(found, policy) for found in programs.collected()]
    return sorted(groups, key=lambda g: g.rss, reverse=True)


class _Programs:
    """Disjoint sets of units. The unit a set is known by is its first: the host, or the oldest."""

    def __init__(self, units: Sequence[_Unit]):
        self._units = {unit.key: unit for unit in units}
        self._head = {unit.key: unit.key for unit in units}

    def join_started_units(self, processes: Sequence[Process]) -> None:
        """A unit nobody recognises (a terminal tab, an agent session) joins the app that started it."""
        owner = {p.pid.value: p.group for p in processes}
        for unit in self._units.values():
            if unit.identity.recognised:
                continue
            hosts = Counter(owner[p.ppid] for p in unit.processes
                            if p.ppid in owner and owner[p.ppid] != unit.key and self._units[owner[p.ppid]].app_like)
            if hosts:
                self._join(hosts.most_common(1)[0][0], unit.key)

    def join_same_identity(self) -> None:
        """Chromium and Electron move their main process into a unit of its own: one app, two units.
        The name alone decides: two desktop entries of one app can differ in icon."""
        first: dict[str, GroupKey] = {}
        for unit in self._units.values():
            if unit.app_like and unit.identity.recognised:
                self._join(first.setdefault(unit.identity.name.casefold(), unit.key), unit.key)

    def collected(self) -> list[list[_Unit]]:
        sets: dict[GroupKey, list[_Unit]] = defaultdict(list)
        for unit in self._units.values():
            sets[self._find(unit.key)].append(unit)
        return [[self._units[head], *(u for u in found if u.key != head)] for head, found in sets.items()]

    def _find(self, key: GroupKey) -> GroupKey:
        while self._head[key] != key:
            key = self._head[key]
        return key

    def _join(self, host: GroupKey, guest: GroupKey) -> None:
        host, guest = self._find(host), self._find(guest)
        if host != guest:
            self._head[guest] = host


def _group(units: list[_Unit], policy: ProtectionPolicy) -> ProcessGroup:
    head = units[0]
    by_memory = tuple(sorted((p for unit in units for p in unit.processes), key=lambda p: p.rss, reverse=True))
    identity = next((u.identity for u in units if u.identity.recognised), head.identity)
    return ProcessGroup(key=head.key, keys=tuple(u.key for u in units), identity=identity, processes=by_memory,
                        protected=any(policy.is_protected(p) for p in by_memory),
                        placed=_section(units, identity))


def _section(units: list[_Unit], identity: Identity) -> Section:
    """A window makes an application, whatever started it. A helper Hyprland started
    with no window and no desktop entry is a service."""
    head = units[0]
    if any(unit.identity.windowed for unit in units):
        return Section.APPS
    if head.app_like and is_bare_command(head.key.value) and not identity.recognised:
        return Section.SYSTEM
    return Section.of(head.key)
