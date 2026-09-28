"""Collects processes into programs, one group per cgroup unit."""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from .model import GroupKey, Process, ProcessGroup
from .naming import Namer
from .safety import ProtectionPolicy


def group_processes(processes: Sequence[Process], namer: Namer, policy: ProtectionPolicy) -> list[ProcessGroup]:
    members: dict[GroupKey, list[Process]] = defaultdict(list)
    for process in processes:
        members[process.group].append(process)
    groups = [_group(key, found, namer, policy) for key, found in members.items()]
    return sorted(groups, key=lambda g: g.rss, reverse=True)


def _group(key: GroupKey, processes: list[Process], namer: Namer, policy: ProtectionPolicy) -> ProcessGroup:
    by_memory = tuple(sorted(processes, key=lambda p: p.rss, reverse=True))
    return ProcessGroup(key=key, identity=namer.identify(by_memory), processes=by_memory,
                        protected=any(policy.is_protected(p) for p in by_memory))
