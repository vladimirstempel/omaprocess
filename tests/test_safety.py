import unittest

from omaprocess.model import GroupKey, Pid, Process, Refused
from omaprocess.safety import ProtectionPolicy


def process(pid, comm="x", uid=1000):
    return Process(pid=Pid(pid), ppid=1, uid=uid, comm=comm, exe="", cmd=comm, rss=1,
                   cpu_ticks=0, start_ticks=0, group=GroupKey("app-x.scope"))


class ProtectionPolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = ProtectionPolicy(uid=1000, untouchable=frozenset({500, 501}))

    def test_protected_processes(self):
        for p in [process(1), process(500), process(9, "quickshell"), process(9, "qs"),
                  process(9, "omarchy-shell"), process(9, uid=0)]:
            with self.subTest(pid=p.pid, comm=p.comm, uid=p.uid):
                self.assertTrue(self.policy.is_protected(p))

    def test_ordinary_process_is_not_protected(self):
        self.assertFalse(self.policy.is_protected(process(42, "chromium")))

    def test_ensure_allowed_refuses_empty_other_uid_and_protected(self):
        cases = {
            "no such": [],
            "another user": [process(42, uid=0)],
            "protected": [process(42, "chromium"), process(43, "quickshell")],
        }
        for message, processes in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(Refused, message):
                    self.policy.ensure_allowed(processes)

    def test_ensure_allowed_passes_ordinary_processes(self):
        self.policy.ensure_allowed([process(42, "chromium")])
