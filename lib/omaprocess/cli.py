"""Command line entry and composition root: the only place that wires real collaborators."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from .cpu import CpuSampler
from .desktop import DesktopCatalog
from .grouping import group_processes
from .model import Refused
from .naming import default_namer
from .procfs import ProcFs
from .safety import ProtectionPolicy
from .snapshot import snapshot
from .windows import HyprlandWindows, NoWindows


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.handler(args, env)
    except Refused as error:
        print(f"omaprocess: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omaprocess", description="List and end your programs.")
    parser.add_argument("--proc", default="/proc", help=argparse.SUPPRESS)
    parser.add_argument("--apps", action="append", help=argparse.SUPPRESS)
    parser.add_argument("--no-hypr", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--uid", type=int, default=os.getuid(), help=argparse.SUPPRESS)
    commands = parser.add_subparsers(required=True, metavar="{list,stop,kill-unit,term,kill}")
    commands.add_parser("list", help="print running programs as JSON").set_defaults(handler=_list)
    return parser


def _list(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    policy = _policy(args)
    catalog = DesktopCatalog.load([Path(d) for d in args.apps] if args.apps else _application_dirs(env))
    windows = NoWindows() if args.no_hypr else HyprlandWindows.query()
    processes = CpuSampler(_state_file(env)).apply(ProcFs(Path(args.proc)).scan(args.uid))
    groups = group_processes(processes, default_namer(catalog, windows), policy)
    json.dump(snapshot(groups, policy), sys.stdout)
    return 0


def _policy(args: argparse.Namespace) -> ProtectionPolicy:
    return ProtectionPolicy(uid=args.uid, untouchable=frozenset({os.getpid(), os.getppid()}))


def _application_dirs(env: Mapping[str, str]) -> list[Path]:
    home = env.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    shared = (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    return [Path(d) / "applications" for d in [home, *shared] if d]


def _state_file(env: Mapping[str, str]) -> Path:
    return Path(env.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "omaprocess" / "cpu.json"
