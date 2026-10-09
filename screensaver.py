#!/usr/bin/env python3
"""Install or audit Yosecula's Matrix screensaver and desktop integration."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGES = ("foot", "ttfx", "jq", "socat")
HYPRLAND_INCLUDE = 'dofile(os.getenv("HOME") .. "/.config/hypr/matrix-screensaver.lua")'


def configured_shell(current: dict) -> dict:
    desired = json.loads(json.dumps(current))
    desired.setdefault("idle", {}).update({"screensaver": 600, "lock": 1800,
                                          "inhibitVlcPlayback": True})
    plugins = desired.setdefault("plugins", [])
    if not any(item.get("id") == "cph.idle" for item in plugins):
        plugins.append({"id": "cph.idle"})
    for field, value in (("disabledPlugins", "omarchy.idle"), ("cloneSourceRestores", "cph.idle")):
        items = desired.setdefault(field, [])
        if value not in items:
            items.append(value)
    return desired


def configured_menu(content: str) -> str:
    action = '"system.screensaver": {"action":"$HOME/.local/bin/omarchy-launch-matrix-screensaver force"}'
    pattern = re.compile(r'"system\.screensaver"\s*:\s*\{[^\n]*\}')
    if pattern.search(content):
        return pattern.sub(lambda _: action, content)
    end = content.rfind("}")
    if end < 0 or "{" not in content:
        raise ValueError("unexpected menu JSONC structure")
    prefix = content[:end].rstrip()
    meaningful = [line.strip() for line in prefix.splitlines()
                  if line.strip() and not line.lstrip().startswith("//")]
    comma = "," if len(meaningful) > 1 and not meaningful[-1].endswith(",") else ""
    return prefix + comma + "\n  " + action + "\n" + content[end:]


def desired_files(home: Path) -> list[tuple[Path, bytes, bool]]:
    files = []
    for name in ("omarchy-launch-matrix-screensaver", "omarchy-screensaver-matrix"):
        files.append((home / ".local/bin" / name, (ROOT / "screensaver/matrix" / name).read_bytes(), True))
    files.append((home / ".config/omarchy/matrix/screensaver.ini",
                  (ROOT / "screensaver/matrix/screensaver.ini").read_bytes(), False))
    files.append((home / ".config/omarchy/matrix/glyphs.json",
                  (ROOT / "screensaver/matrix/glyphs.json").read_bytes(), False))
    for source in sorted((ROOT / "screensaver/matrix/fonts").iterdir()):
        if source.is_file():
            files.append((home / ".local/share/fonts/yosecula" / source.name, source.read_bytes(), False))
    files.append((home / ".config/hypr/matrix-screensaver.lua",
                  (ROOT / "screensaver/matrix/screensaver.lua").read_bytes(), False))
    hyprland = home / ".config/hypr/hyprland.lua"
    content = hyprland.read_text() if hyprland.exists() else ""
    if HYPRLAND_INCLUDE not in (line.strip() for line in content.splitlines()):
        content = content.rstrip() + "\n\n-- Yosecula Matrix screensaver over the desktop wallpaper.\n" + HYPRLAND_INCLUDE + "\n"
    files.append((hyprland, content.encode(), False))
    files.append((home / ".config/omarchy/branding/screensaver.txt",
                  (ROOT / "screensaver/matrix/screensaver.txt").read_bytes(), False))
    for source in sorted((ROOT / "screensaver/cph.idle").iterdir()):
        if source.is_file():
            files.append((home / ".config/omarchy/plugins/cph.idle" / source.name, source.read_bytes(), False))
    files.append((home / ".config/omarchy/hooks/theme-set.d/yosecula-screensaver",
                  (ROOT / "screensaver/theme-set").read_bytes(), True))

    shell = home / ".config/omarchy/shell.json"
    current = json.loads(shell.read_text()) if shell.exists() else {"version": 1}
    desired = configured_shell(current)
    # Avoid a rewrite just to normalize whitespace or escaping.
    content = shell.read_bytes() if desired == current else (json.dumps(desired, indent=2, ensure_ascii=False) + "\n").encode()
    files.append((shell, content, False))
    menu = home / ".config/omarchy/extensions/omarchy-menu.jsonc"
    files.append((menu, configured_menu(menu.read_text() if menu.exists() else "{}\n").encode(), False))

    active_name = home / ".local/state/omarchy/current/theme.name"
    if active_name.exists() and active_name.read_text().strip().lower() == "yosecula":
        files.append((active_name.parent / "theme/matrix.json", (ROOT / "matrix.json").read_bytes(), False))
    return files


def audit(home: Path) -> dict:
    try:
        files = desired_files(home)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return {"state": "blocked", "detail": str(error), "explanation": str(error)}
    missing_packages = [name for name in PACKAGES if not shutil.which(name)]
    missing, changed, blocked, explanations = [], [], [], []
    for target, desired, executable in files:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            blocked.append(f"refusing to replace conflicting path: {target}")
            continue
        if not target.exists():
            missing.append(target)
            explanations.append(f"Create {target}.")
            continue
        current = target.read_bytes()
        executable_changed = bool(target.stat().st_mode & 0o111) != executable
        if current != desired or executable_changed:
            changed.append(target)
            try:
                diff = difflib.unified_diff(current.decode().splitlines(), desired.decode().splitlines(),
                                           fromfile=f"{target} (current)", tofile=f"{target} (desired)", lineterm="")
                explanations.append("\n".join(diff))
            except UnicodeDecodeError:
                explanations.append(f"Replace {target} ({len(current)} → {len(desired)} bytes).")
            if executable_changed:
                explanations.append(f"{target}: executable {not executable} → {executable}")
    if missing_packages:
        explanations.append("Install packages: " + ", ".join(missing_packages))
    state = "blocked" if blocked else "missing" if missing or missing_packages else "drift" if changed else "ok"
    detail = "; ".join(blocked) if blocked else f"{len(missing)} missing, {len(changed)} changed"
    if missing_packages and not blocked:
        detail += "; missing packages: " + ", ".join(missing_packages)
    return {"state": state, "detail": detail,
            "explanation": "\n\n".join([*blocked, *filter(None, explanations)])}


def install(home: Path) -> Path | None:
    status = audit(home)
    if status["state"] == "blocked":
        raise ValueError(status["detail"])
    missing_packages = [name for name in PACKAGES if not shutil.which(name)]
    if missing_packages:
        subprocess.run(["omarchy", "pkg", "add", *missing_packages], check=True)
    # Build the plan again after dependency installation; preserve any newer settings.
    files = desired_files(home)
    backup_root = home / ".local/state/yosecula/backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backed_up = False
    hyprland_changed = False
    fonts_changed = False
    for target, content, executable in files:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"refusing to replace conflicting path: {target}")
        if (target.is_file() and target.read_bytes() == content
                and bool(target.stat().st_mode & 0o111) == executable):
            continue
        if target.exists():
            destination = backup_root / target.relative_to(home)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
            backed_up = True
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o755 if executable else 0o644)
        if target.parent == home / ".config/hypr":
            hyprland_changed = True
        if target.suffix == ".ttf" and target.parent == home / ".local/share/fonts/yosecula":
            fonts_changed = True
    if fonts_changed and home == Path.home():
        subprocess.run(["fc-cache", "-f", str(home / ".local/share/fonts/yosecula")], check=True)
    if hyprland_changed and home == Path.home() and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        subprocess.run(["hyprctl", "reload"], check=True)
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
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Yosecula screensaver installation failed: {error}")
        return 1
    print("Yosecula Matrix screensaver installed (wallpaper background, Foot, 60 FPS, VLC playback inhibition).")
    if backup_root:
        print(f"Previous files backed up under {backup_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
