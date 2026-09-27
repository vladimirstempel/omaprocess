import unittest

from omaprocess.model import GroupKey, Identity, Pid, Process, ProcessGroup, Refused, Section


def process(pid, group="app-x.scope", rss=100, cpu=0.0):
    return Process(pid=Pid(pid), ppid=1, uid=1000, comm="x", exe="/usr/bin/x", cmd="x",
                   rss=rss, cpu_ticks=0, start_ticks=0, group=GroupKey(group), cpu=cpu)


class PidTest(unittest.TestCase):
    def test_parse_accepts_digits(self):
        self.assertEqual(Pid.parse("42"), Pid(42))

    def test_parse_refuses_non_digits(self):
        for text in ["", "-1", "4x", "0"]:
            with self.subTest(text=text), self.assertRaises(Refused):
                Pid.parse(text)

    def test_zero_is_invalid(self):
        with self.assertRaises(ValueError):
            Pid(0)


class GroupKeyTest(unittest.TestCase):
    def test_escaped_scope_is_a_unit(self):
        self.assertTrue(GroupKey(r"app-Hyprland-gtk\x2dlaunch-b4ca519e.scope").is_unit)

    def test_pid_key_is_not_a_unit(self):
        self.assertFalse(GroupKey("pid-7").is_unit)

    def test_for_cgroup_takes_last_segment(self):
        key = GroupKey.for_cgroup("/user.slice/user@1000.service/app.slice/app-slack-7784.scope", Pid(9))
        self.assertEqual(key, GroupKey("app-slack-7784.scope"))

    def test_for_cgroup_without_path_falls_back_to_pid(self):
        self.assertEqual(GroupKey.for_cgroup("", Pid(9)), GroupKey("pid-9"))

    def test_parse_refuses_slashes_and_empty(self):
        for text in ["", "../x.scope", "a/b.service"]:
            with self.subTest(text=text), self.assertRaises(Refused):
                GroupKey.parse(text)


class SectionTest(unittest.TestCase):
    def test_apps_and_system(self):
        cases = {
            "app-slack-7784.scope": Section.APPS,
            "app-org.kde.kdeconnect.daemon@autostart.service": Section.APPS,
            "kitty-3273025-0.scope": Section.APPS,
            r"app-dbus\x2d:1.2\x2dorg.a11y.Bus@0.service": Section.SYSTEM,
            "pipewire.service": Section.SYSTEM,
            "wayland-wm@hyprland.desktop.service": Section.SYSTEM,
            "session-2.scope": Section.SYSTEM,
        }
        for key, section in cases.items():
            with self.subTest(key=key):
                self.assertIs(Section.of(GroupKey(key)), section)


class ProcessGroupTest(unittest.TestCase):
    def test_totals(self):
        group = ProcessGroup(key=GroupKey("app-x.scope"), identity=Identity("X"),
                             processes=(process(1, rss=100, cpu=1.25), process(2, rss=50, cpu=2.0)),
                             protected=False)
        self.assertEqual((group.count, group.rss, group.cpu), (2, 150, 3.2))
        self.assertIs(group.section, Section.APPS)

    def test_exe_name(self):
        self.assertEqual(process(1).exe_name, "x")
