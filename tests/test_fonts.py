import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fonts

RUN = subprocess.run


class DesktopFontTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.hook = self.home / ".config/omarchy/hooks/theme-set.d/yosecula-fonts"
        self.settings = {
            ("org.gnome.desktop.interface", "font-name"): "Adwaita Sans 11",
            ("org.gnome.desktop.interface", "monospace-font-name"): "Adwaita Mono 11",
            ("org.gnome.desktop.wm.preferences", "titlebar-font"): "Adwaita Sans Bold 11",
            ("org.gnome.desktop.interface", "color-scheme"): "prefer-dark",
        }
        self.available = True
        self.writable = True
        self.commands = []
        for patch in (mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test-session"}),
                      mock.patch.object(fonts.subprocess, "run", side_effect=self.command)):
            patch.start()
            self.addCleanup(patch.stop)

    def command(self, args, **kwargs):
        args = tuple(args)
        self.commands.append(args)
        result = ""
        if args[0] == "fc-list":
            result = "JetBrainsMono Nerd Font,JetBrainsMono NF\n" if self.available else "Adwaita Sans\n"
        elif args[:2] == ("gsettings", "get"):
            result = repr(self.settings[args[2:4]])
        elif args[:2] == ("gsettings", "writable"):
            result = "true" if self.writable else "false"
        elif args[:2] == ("gsettings", "set"):
            self.settings[args[2:4]] = args[4]
        elif args[:3] == ("omarchy", "pkg", "add"):
            self.available = True
        elif args[:3] == ("omarchy", "hook", "install"):
            self.hook.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args[4], self.hook)
            self.hook.chmod(0o755)
        else:
            self.fail(f"unexpected command: {args}")
        return subprocess.CompletedProcess(args, 0, result, "")

    def mutations(self):
        return [args for args in self.commands
                if args[0] == "omarchy" or args[:2] == ("gsettings", "set")]

    def test_audit_is_read_only_and_install_backs_up_then_converges(self):
        original = self.settings.copy()
        status = fonts.audit(self.home)
        self.assertEqual(status["state"], "missing")
        self.assertIn("Adwaita Sans 11 → JetBrainsMono Nerd Font 11", status["explanation"])
        self.assertEqual(self.mutations(), [])
        backup = fonts.install(self.home)
        previous = json.loads((backup / "desktop-fonts.json").read_text())
        self.assertEqual(previous, {
            "org.gnome.desktop.interface": {"font-name": "Adwaita Sans 11", "monospace-font-name": "Adwaita Mono 11"},
            "org.gnome.desktop.wm.preferences": {"titlebar-font": "Adwaita Sans Bold 11"},
        })
        self.assertEqual(self.settings[("org.gnome.desktop.interface", "font-name")], "JetBrainsMono Nerd Font 11")
        self.assertEqual(self.settings[("org.gnome.desktop.interface", "monospace-font-name")], "JetBrainsMono Nerd Font 11")
        self.assertEqual(self.settings[("org.gnome.desktop.wm.preferences", "titlebar-font")], "JetBrainsMono Nerd Font Bold 11")
        self.assertEqual(self.settings[("org.gnome.desktop.interface", "color-scheme")],
                         original[("org.gnome.desktop.interface", "color-scheme")])
        self.assertEqual(fonts.audit(self.home)["state"], "ok")
        self.commands.clear()
        self.assertIsNone(fonts.install(self.home))
        self.assertEqual(self.mutations(), [])

    def test_missing_font_is_installed_before_settings_are_written(self):
        self.available = False
        self.assertIn("Install ttf-jetbrains-mono-nerd", fonts.audit(self.home)["explanation"])
        fonts.install(self.home)
        self.assertEqual(self.mutations()[0], ("omarchy", "pkg", "add", "ttf-jetbrains-mono-nerd"))
        self.assertEqual(fonts.audit(self.home)["state"], "ok")

    def test_failed_dependency_install_does_not_write_settings(self):
        command = self.command

        def failed_install(args, **kwargs):
            if tuple(args[:3]) == ("omarchy", "pkg", "add"):
                raise subprocess.CalledProcessError(1, args)
            return command(args, **kwargs)

        self.available = False
        with mock.patch.object(fonts.subprocess, "run", side_effect=failed_install), \
             self.assertRaises(subprocess.CalledProcessError):
            fonts.install(self.home)
        self.assertEqual(self.mutations(), [])
        self.assertFalse(self.hook.exists())

    def test_locked_setting_blocks_before_any_changes(self):
        self.writable = False
        self.assertEqual(fonts.audit(self.home)["state"], "blocked")
        with self.assertRaisesRegex(ValueError, "not writable"):
            fonts.install(self.home)
        self.assertEqual(self.mutations(), [])

    def test_failed_settings_read_is_blocked(self):
        with mock.patch.object(fonts.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "gsettings")):
            self.assertEqual(fonts.audit(self.home)["state"], "blocked")

    def test_silent_settings_write_failure_is_detected(self):
        command = self.command

        def ignored_write(args, **kwargs):
            if tuple(args[:2]) == ("gsettings", "set"):
                return subprocess.CompletedProcess(args, 0, "", "dconf write failed")
            return command(args, **kwargs)

        with mock.patch.object(fonts.subprocess, "run", side_effect=ignored_write), \
             self.assertRaisesRegex(ValueError, "verification failed"):
            fonts.install(self.home)

    def test_conflicting_hook_is_preserved(self):
        self.hook.parent.mkdir(parents=True)
        outside = self.home / "personal-hook"
        outside.write_text("keep my hook\n")
        self.hook.symlink_to(outside)
        self.assertEqual(fonts.audit(self.home)["state"], "blocked")
        with self.assertRaisesRegex(ValueError, "conflicting path"):
            fonts.install(self.home)
        self.assertEqual(outside.read_text(), "keep my hook\n")
        self.assertEqual(self.mutations(), [])

    def test_hook_drift_is_backed_up_and_other_hooks_are_preserved(self):
        fonts.install(self.home)
        self.hook.write_text("old Yosecula hook\n")
        other = self.hook.parent / "personal"
        other.write_text("personal hook\n")
        self.assertEqual(fonts.audit(self.home)["state"], "drift")
        backup = fonts.install(self.home)
        self.assertEqual((backup / self.hook.relative_to(self.home)).read_text(), "old Yosecula hook\n")
        self.assertEqual(other.read_text(), "personal hook\n")

    def test_missing_session_blocks_without_running_commands(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fonts.audit(self.home)["state"], "blocked")
            with self.assertRaisesRegex(ValueError, "D-Bus session"):
                fonts.install(self.home)
        self.assertEqual(self.commands, [])

    def test_theme_hook_runs_only_for_yosecula(self):
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        capture = self.home / "called"
        python = bin_dir / "python3"
        python.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE"\n')
        python.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home), CAPTURE=str(capture),
                   PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
        RUN(["bash", str(fonts.HOOK), "tokyo-night"], env=env, check=True)
        self.assertFalse(capture.exists())
        RUN(["bash", str(fonts.HOOK), "Yosecula"], env=env, check=True)
        self.assertEqual(capture.read_text().strip(), str(self.home / ".config/omarchy/themes/yosecula/fonts.py"))


if __name__ == "__main__":
    unittest.main()
