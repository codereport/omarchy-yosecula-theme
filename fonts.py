#!/usr/bin/env python3
"""Install or audit Yosecula's JetBrains Mono desktop fonts."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FAMILY = "JetBrainsMono Nerd Font"
PACKAGE = "ttf-jetbrains-mono-nerd"
SETTINGS = (
    ("org.gnome.desktop.interface", "font-name", f"{FAMILY} 11"),
    ("org.gnome.desktop.interface", "monospace-font-name", f"{FAMILY} 11"),
    ("org.gnome.desktop.wm.preferences", "titlebar-font", f"{FAMILY} Bold 11"),
)
HOOK = ROOT / "fonts/yosecula-fonts"


def output(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def plan(home: Path) -> tuple[bool, list[tuple[str, str, str, str]], Path, bool]:
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise ValueError("desktop fonts need a user D-Bus session; run from your logged-in desktop")
    families = {family.strip() for line in output("fc-list", "--format", "%{family}\n").splitlines()
                for family in line.split(",")}
    changes = []
    for schema, key, desired in SETTINGS:
        current = ast.literal_eval(output("gsettings", "get", schema, key))
        if not isinstance(current, str):
            raise ValueError(f"{schema} {key}: expected a font name")
        if current != desired:
            if output("gsettings", "writable", schema, key) != "true":
                raise ValueError(f"{schema} {key}: setting is not writable")
            changes.append((schema, key, current, desired))
    hook = home / ".config/omarchy/hooks/theme-set.d/yosecula-fonts"
    if hook.is_symlink() or (hook.exists() and not hook.is_file()):
        raise ValueError(f"refusing to replace conflicting path: {hook}")
    hook_changed = not (hook.is_file() and hook.read_bytes() == HOOK.read_bytes()
                        and hook.stat().st_mode & 0o111)
    return FAMILY not in families, changes, hook, hook_changed


def audit(home: Path) -> dict:
    try:
        missing_font, changes, hook, hook_changed = plan(home)
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        return {"state": "blocked", "detail": str(error), "explanation": str(error)}
    explanations = [f"{schema} {key}: {current} → {desired}"
                    for schema, key, current, desired in changes]
    if missing_font:
        explanations.append(f"Install {PACKAGE} for {FAMILY}.")
    if hook_changed:
        explanations.append(f"Install Yosecula's font theme-set hook at {hook}.")
    state = ("missing" if missing_font or not hook.exists() else
             "drift" if changes or hook_changed else "ok")
    return {"state": state, "detail": f"{FAMILY}, size 11", "explanation": "\n".join(explanations)}


def install(home: Path) -> Path | None:
    missing_font, changes, hook, hook_changed = plan(home)
    if missing_font:
        subprocess.run(["omarchy", "pkg", "add", PACKAGE], check=True)
        missing_font, changes, hook, hook_changed = plan(home)
        if missing_font:
            raise ValueError(f"{FAMILY} is still unavailable after installing {PACKAGE}")
    backup_root = home / ".local/state/yosecula/backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backed_up = False
    if changes:
        previous = {}
        for schema, key, current, _ in changes:
            previous.setdefault(schema, {})[key] = current
        backup_root.mkdir(parents=True)
        (backup_root / "desktop-fonts.json").write_text(json.dumps(previous, indent=2) + "\n")
        backed_up = True
    if hook_changed and hook.exists():
        destination = backup_root / hook.relative_to(home)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hook, destination)
        backed_up = True
    for schema, key, _, desired in changes:
        subprocess.run(["gsettings", "set", schema, key, desired], check=True)
    if hook_changed:
        subprocess.run(["omarchy", "hook", "install", "theme-set", str(HOOK)], check=True)
    status = audit(home)
    if status["state"] != "ok":
        raise ValueError("desktop font verification failed: " + (status["explanation"] or status["detail"]))
    return backup_root if backed_up else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="audit only")
    parser.add_argument("--json", action="store_true", help="machine-readable audit output")
    args = parser.parse_args()
    if args.json and not args.check:
        parser.error("--json requires --check")
    home = Path.home()
    if args.check:
        status = audit(home)
        print(json.dumps(status) if args.json else status["state"] + ": " + status["detail"])
        return 1 if status["state"] == "blocked" else 0
    try:
        backup_root = install(home)
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        print(f"Yosecula desktop font installation failed: {error}")
        return 1
    print(f"Yosecula desktop fonts installed ({FAMILY}, size 11, bold title bars).")
    if backup_root:
        print(f"Previous settings backed up under {backup_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
