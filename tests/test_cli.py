import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fakes import FakeProc, write_desktop
from omaprocess.cli import main

ROOT = Path(__file__).resolve().parent.parent


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.proc = FakeProc(self.dir / "proc")
        (self.dir / "proc").mkdir()
        self.apps = self.dir / "apps"
        self.env = {"XDG_RUNTIME_DIR": str(self.dir / "run")}

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--proc", str(self.dir / "proc"), "--apps", str(self.apps), "--no-hypr",
                         "--uid", "1000", *args], self.env)
        return code, out.getvalue(), err.getvalue()

    def test_list_names_steam_behind_bash(self):
        write_desktop(self.apps, "steam", name="Steam", exec_line="/usr/bin/steam %U", icon="steam")
        self.proc.add(10, "bash", group=r"app-Hyprland-gtk\x2dlaunch-c2a96598.scope", start=1)
        self.proc.add(11, "steam", group=r"app-Hyprland-gtk\x2dlaunch-c2a96598.scope", start=2, rss_kb=900)
        self.proc.add(12, "pipewire", group="pipewire.service")
        self.proc.add(13, "sshd", uid=0, group="sshd.service")
        code, out, err = self.run_cli("list")
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        self.assertEqual([(g["name"], g["icon"], g["count"]) for g in data["apps"]], [("Steam", "steam", 2)])
        self.assertEqual([g["name"] for g in data["system"]], ["Pipewire"])

    def test_list_writes_cpu_state_under_runtime_dir(self):
        self.proc.add(10, "zed")
        self.run_cli("list")
        self.assertTrue((self.dir / "run" / "omaprocess" / "cpu.json").exists())

    def test_launcher_runs(self):
        result = subprocess.run([str(ROOT / "bin" / "omaprocess"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("list", result.stdout)
