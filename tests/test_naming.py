import json
import subprocess
import unittest

from omaprocess.desktop import DesktopCatalog, DesktopEntry
from omaprocess.model import GroupKey, Identity, Pid, Process
from omaprocess.naming import default_namer
from omaprocess.windows import HyprlandWindows, NoWindows


def process(pid, comm, exe=None, start=100):
    return Process(pid=Pid(pid), ppid=1, uid=1000, comm=comm, exe=exe or f"/usr/bin/{comm}", cmd=comm,
                   rss=1, cpu_ticks=0, start_ticks=start, group=GroupKey("app-x.scope"))


def entry(desktop_id, name, executable, icon="", wm_class=""):
    return DesktopEntry(id=desktop_id, name=name, icon=icon, executable=executable, wm_class=wm_class)


CATALOG = DesktopCatalog([
    entry("chromium", "Chromium", "chromium", icon="chromium", wm_class="chromium"),
    entry("whatsapp", "WhatsApp", "omarchy-launch-webapp", wm_class="chrome-web.whatsapp.com__-Default"),
    entry("steam", "Steam", "steam", icon="steam"),
])


def windows(*clients):
    return HyprlandWindows(json.dumps([{"pid": pid, "class": cls} for pid, cls in clients]))


class NamerTest(unittest.TestCase):
    def test_window_whose_entry_matches_the_process_wins(self):
        namer = default_namer(CATALOG, windows((10, "chrome-web.whatsapp.com__-Default"), (10, "chromium")))
        self.assertEqual(namer.identify([process(10, "chromium")]), Identity("Chromium", "chromium"))

    def test_window_class_without_entry_is_prettified(self):
        namer = default_namer(CATALOG, windows((10, "dev.zed.Zed")))
        self.assertEqual(namer.identify([process(10, "zed-editor")]).name, "Zed")

    def test_executable_match_skips_wrappers_oldest_first(self):
        namer = default_namer(CATALOG, NoWindows())
        group = [process(3, "steam", start=300), process(1, "bash", start=100),
                 process(2, "srt-logger", start=200)]
        self.assertEqual(namer.identify(group), Identity("Steam", "steam"))

    def test_fallback_is_capitalised_oldest_non_wrapper(self):
        namer = default_namer(CATALOG, NoWindows())
        group = [process(2, "helper", start=200), process(1, "sh", start=100), process(3, "mytool", start=150)]
        self.assertEqual(namer.identify(group), Identity("Mytool"))

    def test_only_wrappers_falls_back_to_oldest(self):
        namer = default_namer(CATALOG, NoWindows())
        self.assertEqual(namer.identify([process(1, "bash")]), Identity("Bash"))


class HyprlandWindowsTest(unittest.TestCase):
    def test_query_failure_gives_no_windows(self):
        def missing(*args, **kwargs):
            raise FileNotFoundError("hyprctl")
        self.assertEqual(HyprlandWindows.query(run=missing).classes_for(Pid(1)), ())

    def test_query_bad_json_gives_no_windows(self):
        def garbage(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="not json", stderr="")
        self.assertEqual(HyprlandWindows.query(run=garbage).classes_for(Pid(1)), ())

    def test_classes_for_lists_every_window_of_a_pid(self):
        self.assertEqual(windows((5, "a"), (5, "b")).classes_for(Pid(5)), ("a", "b"))

    def test_query_wrong_json_shape_gives_no_windows(self):
        def error_response(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout='{"error":"no clients"}', stderr="")
        self.assertEqual(HyprlandWindows.query(run=error_response).classes_for(Pid(1)), ())

    def test_malformed_clients_are_skipped(self):
        self.assertEqual(
            HyprlandWindows(json.dumps(["x", {"pid": "nope", "class": "a"}, {"pid": 5, "class": "b"}])).classes_for(Pid(5)),
            ("b",)
        )
