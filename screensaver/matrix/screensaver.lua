-- Foot disables transparency when it receives a fullscreen state. Keep the
-- compositor fullscreen so other windows and the bar stay hidden, while Foot
-- renders a transparent background over the current desktop wallpaper.
o.window("^org.omarchy.screensaver$", {
  fullscreen_state = "2 0",
  sync_fullscreen = false,
  no_blur = true,
  no_dim = true,
  opacity = "1.0 override 1.0 override 1.0 override",
})
