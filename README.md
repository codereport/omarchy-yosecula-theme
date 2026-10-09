# Yosecula

Yosecula is a dark [Omarchy](https://omarchy.org/) theme with a palette inspired by [Dracula](https://draculatheme.com/) and a purple Yosemite-inspired wallpaper. Its name pairs Yosemite with Dracula.

## Previews

### Wallpaper and palette

[![Yosecula wallpaper with the Dracula mascot and rounded palette swatches in the lower-left corner](https://raw.githubusercontent.com/codereport/omarchy-yosecula-theme/main/preview.png?readme=3)](preview.png)

The Dracula mascot and color swatches sit in the lower-left corner, leaving the purple sky and Half Dome visible. [Open the full-size preview](preview.png).

### Desktop screenshot

[![Yosecula desktop with a terminal and editor on the left and Half Dome visible on the right](desktop-screenshot.webp)](desktop-screenshot.webp)

This desktop screenshot was submitted with the Omarchy themes listing pull request.

## Install

```bash
omarchy theme install https://github.com/codereport/omarchy-yosecula-theme
```

Then select **Yosecula** from Omarchy's theme menu, or run:

```bash
omarchy theme set yosecula
```

To apply the matching desktop fonts, run:

```bash
python3 "$HOME/.config/omarchy/themes/yosecula/fonts.py"
```

This sets regular and monospace GTK app text to **JetBrainsMono Nerd Font 11** and title bars to **JetBrainsMono Nerd Font Bold 11**. It installs `ttf-jetbrains-mono-nerd` if the family is unavailable, and a `theme-set` hook reapplies the settings whenever Yosecula is selected. [post-omarchy-install](https://github.com/codereport/post-omarchy-install) audits and applies this automatically in Essential through `up`. Changed settings are saved in `desktop-fonts.json` under `~/.local/state/yosecula/backups/`. Run from a logged-in desktop session; reopen apps that keep their previous font. Preview with `fonts.py --check`, or `fonts.py --check --json` for machine-readable state and explanations.

To install the matching Matrix rain screensaver, run:

```bash
python3 "$HOME/.config/omarchy/themes/yosecula/screensaver.py"
```

[post-omarchy-install](https://github.com/codereport/post-omarchy-install) runs this installer automatically as part of Essential. The theme owns the launchers, artwork, idle service, menu action, dependency installation, and a `theme-set` hook that refreshes them when Yosecula is selected again. Changed files are backed up under `~/.local/state/yosecula/backups/`. Audit without applying changes with `screensaver.py --check`; add `--json` for machine-readable state and diffs.

The screensaver shows white Matrix rain over your current desktop wallpaper, without blur or dimming. It runs in Foot with software rendering at 60 FPS, reducing GPU pressure on multiple monitors. It starts after 10 idle minutes and runs for 20 minutes before locking at 30 idle minutes; playing VLC inhibits both timers. Existing bar, presentation widgets, and other shell settings are preserved. After installation, Matrix remains the configured screensaver when you switch themes.

The installer adds a dedicated transparent Foot config and a Hyprland rule loaded from `~/.config/hypr/matrix-screensaver.lua`. Hyprland keeps the screensaver fullscreen while reporting a windowed state to Foot, which otherwise disables transparency in fullscreen. Desktop windows and the bar stay hidden; only the wallpaper appears behind the rain. The installer reloads Hyprland when these rules change in a running session.

The rain uses 305 distinct symbols from Dyalog APL, Kap, BQN, Uiua, and TinyAPL, collected from [Array Box](https://github.com/codereport/array-box)'s keyboard maps, glyph names, and primitive references. The installer includes Array Box's APL387 and Uiua386 fonts so every symbol renders. Only individual printable Unicode characters are included; multi-character tokens and function names are skipped. Refresh the committed glyph snapshot with `node screensaver/matrix/update-glyphs.mjs ../array-box`; the installed screensaver does not need Node or an Array Box checkout.

## Contents

- `colors.toml` defines the theme's dark palette.
- `matrix.json` defines the white rain, bright tips, and final text using six-digit RGB hex colors.
- `screensaver/matrix/glyphs.json` contains the combined array language symbols; `fonts/` in the same directory contains their fonts and license notices.
- `screensaver.py` installs and audits the screensaver integration in `screensaver/`.
- `fonts.py` installs and audits the desktop font settings and the theme-change hook in `fonts/`.
- `backgrounds/` contains the wallpaper used by the theme.
- `preview.png` shows the wallpaper, Dracula mascot, and color palette and appears in Omarchy's theme selector.
- `desktop-screenshot.webp` shows Yosecula on a real desktop and was submitted for the Omarchy themes site.

## Matrix colors

The launcher reads `~/.local/state/omarchy/current/theme/matrix.json` at the start of each animation cycle. Omarchy copies this file from the selected theme, so changing themes changes the palette without editing the launcher. Other themes can provide the same three fields (`rain_color_gradient`, `highlight_color`, and `final_gradient_stops`); missing or invalid palettes use Matrix's green defaults. Edit the theme's `matrix.json` and select the theme again to apply new colors.

## Credits

The color palette is inspired by the Dracula color scheme. The Dracula mascot in the preview belongs to [Dracula Theme](https://draculatheme.com/). The wallpaper was created for this theme from [Hu Nhu's Half Dome photograph](https://commons.wikimedia.org/wiki/File:Glacier_Point_View_of_Half_Dome_at_Sunset_at_Yosemite_National_Park.jpg), which the photographer released under CC0. This repository is an independent community theme for Omarchy.

The Matrix launchers and idle service derive from Omarchy; their MIT licenses are included in `screensaver/matrix/` and `screensaver/cph.idle/`. The theme is available under the [MIT license](LICENSE).
