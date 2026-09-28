import shutil
import tempfile
import unittest
from pathlib import Path

from fakes import write_desktop
from omaprocess.desktop import DesktopCatalog, parse_desktop_file
from omaprocess.model import Identity


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_reads_main_section_only(self):
        path = write_desktop(self.dir, "chromium", name="Chromium", exec_line="/usr/bin/chromium %U",
                             icon="chromium", wm_class="chromium")
        entry = parse_desktop_file(path)
        self.assertEqual((entry.id, entry.name, entry.icon, entry.executable, entry.wm_class),
                         ("chromium", "Chromium", "chromium", "chromium", "chromium"))
        self.assertEqual(entry.identity(), Identity("Chromium", "chromium"))

    def test_exec_skips_env_assignments_and_quotes(self):
        path = write_desktop(self.dir, "zed", name="Zed",
                             exec_line='env FOO=1 BAR=2 "/opt/zed app/zed-editor" %F')
        self.assertEqual(parse_desktop_file(path).executable, "zed-editor")

    def test_unbalanced_quotes_still_parse(self):
        path = write_desktop(self.dir, "odd", name="Odd", exec_line='/usr/bin/odd "broken')
        self.assertEqual(parse_desktop_file(path).executable, "odd")

    def test_hidden_entry_is_none(self):
        path = write_desktop(self.dir, "x", name="X", exec_line="x", hidden=True)
        self.assertIsNone(parse_desktop_file(path))


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.user, self.system = self.root / "user", self.root / "system"

    def test_window_class_matches_wm_class_then_id_then_last_segment(self):
        write_desktop(self.system, "slack", name="Slack", exec_line="slack", wm_class="Slack")
        write_desktop(self.system, "dev.zed.Zed", name="Zed", exec_line="zed")
        write_desktop(self.system, "org.telegram.desktop", name="Telegram", exec_line="Telegram")
        catalog = DesktopCatalog.load([self.system])
        self.assertEqual(catalog.find_by_window_class("slack").name, "Slack")
        self.assertEqual(catalog.find_by_window_class("dev.zed.Zed").name, "Zed")
        self.assertEqual(catalog.find_by_window_class("org.telegram.desktop").name, "Telegram")
        self.assertEqual(catalog.find_by_window_class("Zed").name, "Zed")  # last dotted segment of the id
        self.assertIsNone(catalog.find_by_window_class("nothing"))

    def test_executable_prefers_entry_named_after_it(self):
        write_desktop(self.system, "a-webapp", name="WhatsApp", exec_line="chromium --app=x")
        write_desktop(self.system, "chromium", name="Chromium", exec_line="chromium %U")
        catalog = DesktopCatalog.load([self.system])
        self.assertEqual(catalog.find_by_executable("chromium").name, "Chromium")
        self.assertIsNone(catalog.find_by_executable(""))

    def test_earlier_dir_wins_and_hidden_user_entry_hides_system_one(self):
        write_desktop(self.user, "zed", name="My Zed", exec_line="zed")
        write_desktop(self.system, "zed", name="Zed", exec_line="zed")
        write_desktop(self.user, "steam", name="Steam", exec_line="steam", hidden=True)
        write_desktop(self.system, "steam", name="Steam", exec_line="steam")
        catalog = DesktopCatalog.load([self.user, self.system, self.root / "missing"])
        self.assertEqual(catalog.find_by_executable("zed").name, "My Zed")
        self.assertIsNone(catalog.find_by_executable("steam"))
