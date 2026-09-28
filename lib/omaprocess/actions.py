"""Ends programs (whole cgroup units) and single processes, after the policy agrees."""
from __future__ import annotations

import os
import signal
import subprocess

from .model import GroupKey, Pid, Refused
from .procfs import ProcFs
from .safety import ProtectionPolicy


class Terminator:
    def __init__(self, procfs: ProcFs, policy: ProtectionPolicy, uid: int,
                 run=subprocess.run, send=os.kill):
        self._procfs = procfs
        self._policy = policy
        self._uid = uid
        self._run = run
        self._send = send

    def stop_group(self, key: GroupKey) -> None:
        self._end_group(key, ["stop", "--no-block"], signal.SIGTERM)

    def kill_group(self, key: GroupKey) -> None:
        self._end_group(key, ["kill", "-s", "KILL"], signal.SIGKILL)

    def term(self, pid: Pid) -> None:
        self._end_process(pid, signal.SIGTERM)

    def kill(self, pid: Pid) -> None:
        self._end_process(pid, signal.SIGKILL)

    def _end_group(self, key: GroupKey, systemctl_args: list[str], sig: signal.Signals) -> None:
        members = [p for p in self._procfs.scan(self._uid) if p.group == key]
        if not members:
            return  # already gone: same as an already-gone pid, nothing to refuse
        self._policy.ensure_allowed(members)
        if key.is_unit and self._systemctl([*systemctl_args, "--", str(key)]):
            return
        for member in members:
            self._signal(member.pid, sig)

    def _end_process(self, pid: Pid, sig: signal.Signals) -> None:
        process = self._procfs.read(pid)
        if process is None:
            return
        self._policy.ensure_allowed([process])  # best message for other-uid/PID 1/untouchable
        # A single process can pass that check yet still belong to a protected
        # group (e.g. Hyprland runs in the same unit as quickshell); refuse
        # the whole group, not just the one pid, or ending it takes the shell down.
        self._policy.ensure_group_allowed([p for p in self._procfs.scan(self._uid) if p.group == process.group])
        self._signal(pid, sig)

    def _systemctl(self, args: list[str]) -> bool:
        try:
            return self._run(["systemctl", "--user", *args], capture_output=True, timeout=10).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _signal(self, pid: Pid, sig: signal.Signals) -> None:
        try:
            self._send(pid.value, sig)
        except ProcessLookupError:
            return
        except PermissionError:
            raise Refused(f"not permitted to signal process {pid}") from None
