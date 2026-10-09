import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import screensaver


class ScreensaverInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        patch = mock.patch.object(screensaver.shutil, "which", return_value="/usr/bin/available")
        patch.start()
        self.addCleanup(patch.stop)

    def test_install_preserves_other_settings_and_is_idempotent(self):
        hyprland = self.home / ".config/hypr/hyprland.lua"
        hyprland.parent.mkdir(parents=True)
        hyprland.write_text('-- Personal rules\no.window("webcam-viewer", { float = true })\n')
        shell = self.home / ".config/omarchy/shell.json"
        shell.parent.mkdir(parents=True)
        shell.write_text(json.dumps({"version": 1, "bar": {"centerAnchor": "cph.clock"},
                                     "plugins": [{"id": "cph.presentations"}]}))
        menu = shell.parent / "extensions/omarchy-menu.jsonc"
        menu.parent.mkdir()
        menu.write_text('{\n  // Personal apps\n  "personal": {"label": "Personal"}\n}\n')
        active = self.home / ".local/state/omarchy/current/theme.name"
        active.parent.mkdir(parents=True)
        active.write_text("yosecula\n")

        backup = screensaver.install(self.home)
        self.assertEqual(screensaver.audit(self.home)["state"], "ok")
        self.assertEqual((backup / shell.relative_to(self.home)).read_text(),
                         json.dumps({"version": 1, "bar": {"centerAnchor": "cph.clock"},
                                     "plugins": [{"id": "cph.presentations"}]}))
        self.assertEqual((backup / hyprland.relative_to(self.home)).read_text(),
                         '-- Personal rules\no.window("webcam-viewer", { float = true })\n')
        self.assertIn('o.window("webcam-viewer", { float = true })', hyprland.read_text())
        self.assertEqual(hyprland.read_text().count(screensaver.HYPRLAND_INCLUDE), 1)
        data = json.loads(shell.read_text())
        self.assertEqual(data["bar"], {"centerAnchor": "cph.clock"})
        self.assertIn({"id": "cph.presentations"}, data["plugins"])
        self.assertIn({"id": "cph.idle"}, data["plugins"])
        self.assertEqual(data["idle"], {"screensaver": 600, "lock": 1800, "inhibitVlcPlayback": True})
        self.assertIn("omarchy.idle", data["disabledPlugins"])
        self.assertIn("// Personal apps", menu.read_text())
        self.assertIn('"personal": {"label": "Personal"}', menu.read_text())
        self.assertIn("omarchy-launch-matrix-screensaver force", menu.read_text())
        self.assertEqual((active.parent / "theme/matrix.json").read_bytes(),
                         (screensaver.ROOT / "matrix.json").read_bytes())
        launcher = self.home / ".local/bin/omarchy-launch-matrix-screensaver"
        hook = shell.parent / "hooks/theme-set.d/yosecula-screensaver"
        self.assertTrue(launcher.stat().st_mode & 0o111)
        self.assertTrue(hook.stat().st_mode & 0o111)
        self.assertIsNone(screensaver.install(self.home))

    def test_install_reloads_running_hyprland_only_when_its_config_changes(self):
        with mock.patch.object(screensaver.Path, "home", return_value=self.home), \
             mock.patch.dict(screensaver.os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "test"}), \
             mock.patch.object(screensaver.subprocess, "run") as run:
            screensaver.install(self.home)
            self.assertEqual(run.call_args_list, [
                mock.call(["fc-cache", "-f", str(self.home / ".local/share/fonts/yosecula")], check=True),
                mock.call(["hyprctl", "reload"], check=True),
            ])
            run.reset_mock()
            self.assertIsNone(screensaver.install(self.home))
            run.assert_not_called()

    def test_binary_font_drift_is_audited_and_repaired(self):
        screensaver.install(self.home)
        font = self.home / ".local/share/fonts/yosecula/APL387.ttf"
        font.write_bytes(b"\xffbroken font")
        status = screensaver.audit(self.home)
        self.assertEqual(status["state"], "drift")
        self.assertIn(f"Replace {font}", status["explanation"])
        backup = screensaver.install(self.home)
        self.assertEqual((backup / font.relative_to(self.home)).read_bytes(), b"\xffbroken font")
        self.assertEqual(screensaver.audit(self.home)["state"], "ok")

    def test_audit_repairs_missing_wallpaper_rules_without_losing_personal_rules(self):
        screensaver.install(self.home)
        hyprland = self.home / ".config/hypr/hyprland.lua"
        hyprland.write_text('-- Updated personal rules\no.window("my-app", { float = true })\n')
        rules = hyprland.parent / "matrix-screensaver.lua"
        rules.unlink()
        self.assertEqual(screensaver.audit(self.home)["state"], "missing")
        screensaver.install(self.home)
        self.assertEqual(screensaver.audit(self.home)["state"], "ok")
        self.assertIn('o.window("my-app", { float = true })', hyprland.read_text())
        self.assertEqual(hyprland.read_text().count(screensaver.HYPRLAND_INCLUDE), 1)

    def test_conflicts_and_invalid_shell_block_before_files_are_changed(self):
        launcher = self.home / ".local/bin/omarchy-launch-matrix-screensaver"
        launcher.parent.mkdir(parents=True)
        outside = self.home / "keep-me"
        outside.write_text("my launcher")
        launcher.symlink_to(outside)
        self.assertEqual(screensaver.audit(self.home)["state"], "blocked")
        with self.assertRaises(ValueError):
            screensaver.install(self.home)
        self.assertEqual(outside.read_text(), "my launcher")
        self.assertFalse((launcher.parent / "omarchy-screensaver-matrix").exists())
        launcher.unlink()
        shell = self.home / ".config/omarchy/shell.json"
        shell.parent.mkdir(parents=True)
        shell.write_text("{broken")
        self.assertEqual(screensaver.audit(self.home)["state"], "blocked")
        with self.assertRaises(ValueError):
            screensaver.install(self.home)
        self.assertEqual(shell.read_text(), "{broken")
        self.assertFalse(launcher.exists())

    def test_other_active_theme_palette_is_preserved(self):
        active = self.home / ".local/state/omarchy/current"
        (active / "theme").mkdir(parents=True)
        (active / "theme.name").write_text("tokyo-night")
        (active / "theme/matrix.json").write_text('{"custom": true}')
        screensaver.install(self.home)
        self.assertEqual((active / "theme/matrix.json").read_text(), '{"custom": true}')

    def test_missing_dependencies_are_installed_by_the_theme(self):
        with mock.patch.object(screensaver.shutil, "which", side_effect=lambda name: None if name == "foot" else name), \
             mock.patch.object(screensaver.subprocess, "run") as run:
            screensaver.install(self.home)
        run.assert_called_once_with(["omarchy", "pkg", "add", "foot"], check=True)


@unittest.skipUnless(shutil.which("jq"), "jq is needed to read theme palettes")
class MatrixPaletteTests(unittest.TestCase):
    def run_matrix(self, palette, glyphs=None):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            if palette is not None:
                path = home / ".local/state/omarchy/current/theme/matrix.json"
                path.parent.mkdir(parents=True)
                path.write_text(palette)
            if glyphs is not None:
                path = home / ".config/omarchy/matrix/glyphs.json"
                path.parent.mkdir(parents=True)
                path.write_text(glyphs)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            commands = {
                "ttfx": "#!" + sys.executable + "\nimport json, os, sys\n"
                        "from pathlib import Path\nPath(os.environ['MATRIX_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n",
                "pgrep": "#!/bin/bash\nfor ((i=0; i<200; i++)); do\n"
                         '  [[ -f "$MATRIX_CAPTURE" ]] && exit 0\n  sleep 0.01\ndone\nexit 1\n',
                "hyprctl": '#!/bin/bash\n[[ $1 == activewindow ]] && printf \'{"class":"org.omarchy.screensaver"}\\n\'\nexit 0\n',
                "pkill": "#!/bin/bash\nexit 0\n",
                "tty": "#!/bin/bash\nprintf '/dev/pts/test\\n'\n",
                "stty": "#!/bin/bash\nprintf '60 200\\n'\n",
            }
            for name, content in commands.items():
                target = bin_dir / name
                target.write_text(content)
                target.chmod(0o755)
            capture = home / "arguments.json"
            env = dict(os.environ, HOME=str(home), PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                       MATRIX_CAPTURE=str(capture))
            script = screensaver.ROOT / "screensaver/matrix/omarchy-screensaver-matrix"
            subprocess.run(["bash", str(script)], env=env, input="\n", text=True,
                           capture_output=True, check=True, timeout=5)
            return json.loads(capture.read_text())

    def test_yosecula_palette_reaches_matrix_and_keeps_60_fps(self):
        palette = json.loads((screensaver.ROOT / "matrix.json").read_text())
        args = self.run_matrix(json.dumps(palette))
        self.assertEqual(args[args.index("--frame-rate") + 1], "60")
        self.assertEqual(args[args.index("matrix") + 1:], [
            "--rain-color-gradient", *palette["rain_color_gradient"],
            "--highlight-color", palette["highlight_color"],
            "--final-gradient-stops", *palette["final_gradient_stops"],
        ])
        self.assertNotIn("--random-effect", args)

    def test_missing_malformed_and_invalid_palettes_use_green_defaults(self):
        for palette in (None, "{bad json", "{}", "[]",
                        '{"rain_color_gradient":["--no-color"],"highlight_color":"ffffff",'
                        '"final_gradient_stops":["000000"]}'):
            with self.subTest(palette=palette):
                args = self.run_matrix(palette)
                self.assertEqual(args[args.index("matrix") + 1:], [])

    def test_array_language_glyphs_reach_matrix_as_individual_unicode_arguments(self):
        glyphs = json.loads((screensaver.ROOT / "screensaver/matrix/glyphs.json").read_text())
        args = self.run_matrix(None, json.dumps(glyphs))
        self.assertEqual(args[args.index("--rain-symbols") + 1:], glyphs)
        self.assertIn("𝕩", glyphs)
        self.assertIn("⍺", glyphs)
        self.assertIn("⫽", glyphs)
        self.assertIn("⧈", glyphs)
        self.assertIn("߹", glyphs)
        self.assertIn("\\", glyphs)
        self.assertIn("-", glyphs)

    def test_invalid_glyph_lists_use_the_stock_symbols(self):
        for glyphs in ("{bad json", "{}", "[]", '["--no-color"]', '[" "]', '["\\n"]',
                       '["\u0301"]', '["\u0000"]', '[42]'):
            with self.subTest(glyphs=glyphs):
                args = self.run_matrix(None, glyphs)
                self.assertNotIn("--rain-symbols", args)


if __name__ == "__main__":
    unittest.main()
