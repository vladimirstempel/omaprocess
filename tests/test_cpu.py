import shutil
import tempfile
import unittest
from pathlib import Path

from omaprocess.cpu import CpuSampler
from omaprocess.model import GroupKey, Pid, Process


def process(pid, ticks, start=100):
    return Process(pid=Pid(pid), ppid=1, uid=1000, comm="x", exe="", cmd="x", rss=1,
                   cpu_ticks=ticks, start_ticks=start, group=GroupKey("app-x.scope"))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class CpuSamplerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.clock = FakeClock()
        self.sampler = CpuSampler(self.dir / "sub" / "cpu.json", clock=self.clock, ticks_per_second=100)

    def test_first_sample_is_zero(self):
        self.assertEqual([p.cpu for p in self.sampler.apply([process(1, 50)])], [0.0])

    def test_second_sample_is_share_of_one_core(self):
        self.sampler.apply([process(1, 0)])
        self.clock.now += 2.0
        self.assertEqual(self.sampler.apply([process(1, 100)])[0].cpu, 50.0)

    def test_reused_pid_with_new_start_time_is_zero(self):
        self.sampler.apply([process(1, 0, start=100)])
        self.clock.now += 1.0
        self.assertEqual(self.sampler.apply([process(1, 100, start=999)])[0].cpu, 0.0)

    def test_corrupt_state_file_is_ignored(self):
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "cpu.json").write_text("{not json")
        self.assertEqual(self.sampler.apply([process(1, 5)])[0].cpu, 0.0)
