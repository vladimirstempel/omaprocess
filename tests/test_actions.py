import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

from fakes import FakeProc
from omaprocess.actions import Terminator
from omaprocess.model import GroupKey, Pid, Refused
from omaprocess.procfs import ProcFs
from omaprocess.safety import ProtectionPolicy

UNIT = r"app-Hyprland-gtk\x2dlaunch-b4ca519e.scope"


class Recorder:
    def __init__(self, returncode=0, gone=()):
        self.commands, self.signals = [], []
        self.returncode, self.gone = returncode, set(gone)

    def run(self, command, **kwargs):
        self.commands.append(command)
        return subprocess.CompletedProcess(command, self.returncode)

    def send(self, pid, sig):
        if pid in self.gone:
            raise ProcessLookupError(pid)
        self.signals.append((pid, sig))


class TerminatorTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.proc = FakeProc(self.root)
        self.proc.add(10, "chromium", group=UNIT)
        self.proc.add(11, "chromium", group=UNIT)
        self.proc.add(20, "sleep", group="session-2.scope")
        self.proc.add(30, "sshd", uid=0, group="sshd.service")
        self.proc.add(40, "quickshell", group="wayland-wm@hyprland.desktop.service")

    def terminator(self, recorder):
        policy = ProtectionPolicy(uid=1000, untouchable=frozenset())
        return Terminator(ProcFs(self.root), policy, 1000, run=recorder.run, send=recorder.send)

    def test_stop_group_passes_escaped_unit_verbatim_without_blocking(self):
        recorder = Recorder()
        self.terminator(recorder).stop_group(GroupKey(UNIT))
        self.assertEqual(recorder.commands, [["systemctl", "--user", "stop", "--no-block", "--", UNIT]])
        self.assertEqual(recorder.signals, [])

    def test_kill_group_uses_systemctl_kill(self):
        recorder = Recorder()
        self.terminator(recorder).kill_group(GroupKey(UNIT))
        self.assertEqual(recorder.commands, [["systemctl", "--user", "kill", "-s", "KILL", "--", UNIT]])

    def test_group_outside_user_manager_falls_back_to_signals(self):
        recorder = Recorder(returncode=5)
        self.terminator(recorder).stop_group(GroupKey("session-2.scope"))
        self.assertEqual(recorder.signals, [(20, signal.SIGTERM)])

    def test_group_with_the_shell_is_refused(self):
        with self.assertRaisesRegex(Refused, "protected"):
            self.terminator(Recorder()).stop_group(GroupKey("wayland-wm@hyprland.desktop.service"))

    def test_unknown_group_is_refused(self):
        with self.assertRaisesRegex(Refused, "no such"):
            self.terminator(Recorder()).stop_group(GroupKey("app-nothing.scope"))

    def test_term_and_kill_send_signals(self):
        recorder = Recorder()
        terminator = self.terminator(recorder)
        terminator.term(Pid(10))
        terminator.kill(Pid(11))
        self.assertEqual(recorder.signals, [(10, signal.SIGTERM), (11, signal.SIGKILL)])

    def test_process_of_another_user_is_refused(self):
        with self.assertRaisesRegex(Refused, "another user"):
            self.terminator(Recorder()).term(Pid(30))

    def test_process_that_is_already_gone_is_success(self):
        self.terminator(Recorder()).term(Pid(99))  # no /proc entry: nothing to end
        self.terminator(Recorder(gone={10})).term(Pid(10))  # exits between read and signal
