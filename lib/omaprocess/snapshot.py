"""The JSON contract between the helper and the panel."""
from __future__ import annotations

from typing import Sequence

from .model import Process, ProcessGroup, Section
from .safety import ProtectionPolicy


def snapshot(groups: Sequence[ProcessGroup], policy: ProtectionPolicy) -> dict:
    return {section.value: [_group(g, policy) for g in groups if g.section is section] for section in Section}


def _group(group: ProcessGroup, policy: ProtectionPolicy) -> dict:
    return {
        "key": str(group.key),
        "unit": str(group.key) if group.key.is_unit else "",
        "name": group.identity.name,
        "icon": group.identity.icon,
        "count": group.count,
        "rss": group.rss,
        "cpu": group.cpu,
        "protected": group.protected,
        "procs": [_process(p, policy) for p in group.processes],
    }


def _process(process: Process, policy: ProtectionPolicy) -> dict:
    return {"pid": process.pid.value, "comm": process.comm, "cmd": process.cmd, "rss": process.rss,
            "cpu": process.cpu, "protected": policy.is_protected(process)}
