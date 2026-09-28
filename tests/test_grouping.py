import unittest

from omaprocess.grouping import group_processes
from omaprocess.model import GroupKey, Identity, Pid, Process
from omaprocess.safety import ProtectionPolicy
from omaprocess.snapshot import snapshot


def process(pid, group, rss, comm="x"):
    return Process(pid=Pid(pid), ppid=1, uid=1000, comm=comm, exe="", cmd=comm, rss=rss,
                   cpu_ticks=0, start_ticks=pid, group=GroupKey(group))


class StubNamer:
    def identify(self, processes):
        return Identity(processes[0].comm.title(), "icon")


POLICY = ProtectionPolicy(uid=1000, untouchable=frozenset())


class GroupingTest(unittest.TestCase):
    def test_groups_sorted_by_memory_with_processes_sorted_too(self):
        groups = group_processes([process(1, "app-a.scope", 10), process(2, "app-b.scope", 500),
                                  process(3, "app-a.scope", 30)], StubNamer(), POLICY)
        self.assertEqual([str(g.key) for g in groups], ["app-b.scope", "app-a.scope"])
        self.assertEqual([p.pid.value for p in groups[1].processes], [3, 1])

    def test_group_with_the_shell_is_protected(self):
        groups = group_processes([process(1, "wayland-wm@hyprland.desktop.service", 1, "Hyprland"),
                                  process(2, "wayland-wm@hyprland.desktop.service", 1, "quickshell")],
                                 StubNamer(), POLICY)
        self.assertTrue(groups[0].protected)


class SnapshotTest(unittest.TestCase):
    def test_shape_and_sections(self):
        groups = group_processes([process(4, "app-a.scope", 10, "zed"), process(2, "pipewire.service", 5),
                                  process(3, "pid-3", 1, "qs")], StubNamer(), POLICY)
        data = snapshot(groups, POLICY)
        self.assertEqual([g["key"] for g in data["apps"]], ["app-a.scope"])
        self.assertEqual([g["key"] for g in data["system"]], ["pipewire.service", "pid-3"])
        app = data["apps"][0]
        self.assertEqual(app, {"key": "app-a.scope", "unit": "app-a.scope", "name": "Zed", "icon": "icon",
                               "count": 1, "rss": 10, "cpu": 0.0, "protected": False,
                               "procs": [{"pid": 4, "comm": "zed", "cmd": "zed", "rss": 10, "cpu": 0.0,
                                          "protected": False}]})
        self.assertEqual(data["system"][1]["unit"], "")
        self.assertTrue(data["system"][1]["procs"][0]["protected"])

    def test_ordinary_process_in_a_protected_group_is_protected_too(self):
        # "Hyprland" is not itself in the protected-comm list, but it shares
        # its group (the shell's systemd unit) with a "quickshell" process.
        # (pids are >1 and not otherwise untouchable, so only group membership explains it.)
        groups = group_processes([process(10, "wayland-wm@hyprland.desktop.service", 1, "Hyprland"),
                                  process(20, "wayland-wm@hyprland.desktop.service", 1, "quickshell")],
                                 StubNamer(), POLICY)
        data = snapshot(groups, POLICY)
        rows = data["system"][0]["procs"]
        hyprland = next(p for p in rows if p["comm"] == "Hyprland")
        self.assertTrue(hyprland["protected"])
