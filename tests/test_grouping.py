import unittest

from omaprocess.grouping import group_processes
from omaprocess.model import GroupKey, Identity, Pid, Process, Section
from omaprocess.safety import ProtectionPolicy
from omaprocess.snapshot import snapshot


def process(pid, group, rss, comm="x", ppid=0):
    return Process(pid=Pid(pid), ppid=ppid, uid=1000, comm=comm, exe="", cmd=comm, rss=rss,
                   cpu_ticks=0, start_ticks=pid, group=GroupKey(group))


class StubNamer:
    """Names a group after its first process. A capitalised comm stands for a known app."""

    def identify(self, processes):
        comm = processes[0].comm
        return Identity(comm.title(), "icon", recognised=comm[:1].isupper())


HYPRLAND = "wayland-wm@hyprland.desktop.service"


def keys(group):
    return [str(key) for key in group.keys]


POLICY = ProtectionPolicy(uid=1000, untouchable=frozenset())


class GroupingTest(unittest.TestCase):
    def test_groups_sorted_by_memory_with_processes_sorted_too(self):
        groups = group_processes([process(1, "app-a.scope", 10), process(2, "app-b.scope", 500),
                                  process(3, "app-a.scope", 30)], StubNamer(), POLICY)
        self.assertEqual([str(g.key) for g in groups], ["app-b.scope", "app-a.scope"])
        self.assertEqual([p.pid.value for p in groups[1].processes], [3, 1])

    def test_units_with_the_same_app_name_are_one_program(self):
        # Chromium moves its main process into a unit of its own and leaves the rest behind.
        groups = group_processes([process(10, r"app-Hyprland-gtk\x2dlaunch-51848070.scope", 5, "Chromium"),
                                  process(11, "app-org.chromium.Chromium-11.scope", 9, "chromium"),
                                  process(12, "app-slack-12.scope", 1, "Slack")],
                                 type("Namer", (), {"identify": lambda self, found: Identity(
                                     found[0].comm.title(), found[0].comm, recognised=True)})(), POLICY)
        self.assertEqual([(g.identity.name, keys(g)) for g in groups], [
            ("Chromium", [r"app-Hyprland-gtk\x2dlaunch-51848070.scope", "app-org.chromium.Chromium-11.scope"]),
            ("Slack", ["app-slack-12.scope"])])

    def test_unrecognised_unit_joins_the_app_that_started_it(self):
        groups = group_processes([process(10, "app-kitty-10.scope", 5, "Kitty"),
                                  process(11, "kitty-10-0.scope", 1, "bash", ppid=10),
                                  process(12, "kitty-10-1.scope", 1, "bash", ppid=10),
                                  process(13, "t3code-claude-1.scope", 1, "claude", ppid=12)],
                                 StubNamer(), POLICY)
        self.assertEqual([(g.identity.name, len(g.keys), g.count) for g in groups], [("Kitty", 4, 4)])
        self.assertEqual(str(groups[0].key), "app-kitty-10.scope")

    def test_recognised_app_started_from_a_terminal_stays_its_own_program(self):
        groups = group_processes([process(10, "app-kitty-10.scope", 5, "Kitty"),
                                  process(11, "app-zed-11.scope", 1, "Zed", ppid=10)], StubNamer(), POLICY)
        self.assertEqual([g.identity.name for g in groups], ["Kitty", "Zed"])

    def test_service_does_not_join_whatever_started_it(self):
        groups = group_processes([process(10, HYPRLAND, 5, "Hyprland"),
                                  process(11, "kitty-10-0.scope", 1, "bash", ppid=10)], StubNamer(), POLICY)
        self.assertEqual(len(groups), 2)

    def test_helper_hyprland_started_with_no_window_is_a_system_service(self):
        sections = {str(g.key): g.section for g in group_processes([
            process(10, "app-Hyprland-udiskie-ca8700e1.scope", 1, "udiskie"),
            process(11, "app-Hyprland-xfreerdp-d441c427.scope", 1, "Xfreerdp"),
            process(12, r"app-Hyprland-gtk\x2dlaunch-0cd72bd4.scope", 1, "unityhub-bin")], StubNamer(), POLICY)}
        self.assertEqual(sections, {"app-Hyprland-udiskie-ca8700e1.scope": Section.SYSTEM,
                                    "app-Hyprland-xfreerdp-d441c427.scope": Section.APPS,
                                    r"app-Hyprland-gtk\x2dlaunch-0cd72bd4.scope": Section.APPS})

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
        self.assertEqual(app, {"key": "app-a.scope", "keys": ["app-a.scope"], "unit": "app-a.scope", "name": "Zed", "icon": "icon",
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
