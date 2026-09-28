"""Builders for a fake /proc tree and fake .desktop files, shared by the tests."""
import os
from pathlib import Path


class FakeProc:
    def __init__(self, root: Path):
        self.root = root

    def add(self, pid, comm, *, uid=1000, ppid=1, group="app-test.scope", exe=None, cmd=None,
            rss_kb=1024, utime=0, stime=0, start=100, kernel=False):
        directory = self.root / str(pid)
        directory.mkdir(parents=True)
        (directory / "status").write_text(
            f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nVmRSS:\t   {rss_kb} kB\n")
        fields = ["S", str(ppid)] + ["0"] * 9 + [str(utime), str(stime)] + ["0"] * 6 + [str(start)]
        (directory / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + " 0 0\n")
        cgroup = "" if group is None else f"0::/user.slice/user@{uid}.service/app.slice/{group}\n"
        (directory / "cgroup").write_text(cgroup)
        argv = [] if kernel else (cmd or [exe or comm])
        (directory / "cmdline").write_bytes(b"".join(a.encode() + b"\0" for a in argv))
        os.symlink(exe or f"/usr/bin/{comm}", directory / "exe")


def write_desktop(directory, desktop_id, *, name, exec_line, icon="", wm_class="", hidden=False):
    directory.mkdir(parents=True, exist_ok=True)
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Exec={exec_line}"]
    if icon:
        lines.append(f"Icon={icon}")
    if wm_class:
        lines.append(f"StartupWMClass={wm_class}")
    if hidden:
        lines.append("Hidden=true")
    lines += ["", "[Desktop Action new]", "Name=Should Not Win", "Exec=other"]
    path = directory / f"{desktop_id}.desktop"
    path.write_text("\n".join(lines) + "\n")
    return path
