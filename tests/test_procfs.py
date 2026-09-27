import shutil
import tempfile
import unittest
from pathlib import Path

from fakes import FakeProc
from omaprocess.model import GroupKey, Pid
from omaprocess.procfs import ProcFs


class ProcFsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.proc = FakeProc(self.root)
        self.procfs = ProcFs(self.root)

    def test_reads_one_process(self):
        self.proc.add(10, "chromium", ppid=3, group="app-c.scope", exe="/usr/lib/chromium/chromium",
                      cmd=["/usr/lib/chromium/chromium", "--type=renderer"], rss_kb=2,
                      utime=5, stime=7, start=900)
        process = self.procfs.read(Pid(10))
        self.assertEqual(process.pid, Pid(10))
        self.assertEqual(process.ppid, 3)
        self.assertEqual(process.uid, 1000)
        self.assertEqual(process.comm, "chromium")
        self.assertEqual(process.exe_name, "chromium")
        self.assertEqual(process.cmd, "/usr/lib/chromium/chromium --type=renderer")
        self.assertEqual(process.rss, 2048)
        self.assertEqual((process.cpu_ticks, process.start_ticks), (12, 900))
        self.assertEqual(process.group, GroupKey("app-c.scope"))

    def test_comm_with_spaces_and_parens_keeps_fields_aligned(self):
        self.proc.add(11, "tmux: (server)", ppid=4, utime=1, stime=2, start=77)
        process = self.procfs.read(Pid(11))
        self.assertEqual(process.comm, "tmux: (server)")
        self.assertEqual((process.ppid, process.cpu_ticks, process.start_ticks), (4, 3, 77))

    def test_scan_keeps_only_own_uid_and_skips_kernel_threads(self):
        self.proc.add(1, "systemd", uid=0)
        self.proc.add(2, "kthreadd", kernel=True)
        self.proc.add(3, "zed")
        self.assertEqual([p.pid for p in self.procfs.scan(1000)], [Pid(3)])

    def test_process_that_vanished_mid_scan_is_skipped(self):
        self.proc.add(5, "gone")
        (self.root / "5" / "stat").unlink()
        self.proc.add(6, "alive")
        self.assertIsNone(self.procfs.read(Pid(5)))
        self.assertEqual([p.pid for p in self.procfs.scan(1000)], [Pid(6)])

    def test_missing_cgroup_line_groups_by_pid(self):
        self.proc.add(8, "odd", group=None)
        self.assertEqual(self.procfs.read(Pid(8)).group, GroupKey("pid-8"))

    def test_long_command_line_is_truncated(self):
        self.proc.add(9, "java", cmd=["java"] + ["-Dx=" + "y" * 50] * 10)
        self.assertEqual(len(self.procfs.read(Pid(9)).cmd), 200)

    def test_non_numeric_entries_are_ignored(self):
        (self.root / "self").mkdir()
        self.proc.add(3, "zed")
        self.assertEqual(len(self.procfs.scan(1000)), 1)
