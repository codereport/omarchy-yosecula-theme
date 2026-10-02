function secondsFromConfig(value, fallback) {
  var n = Number(value)
  if (!isFinite(n) || n < 0) return fallback
  return Math.floor(n)
}

function eventParts(event, count) {
  try {
    if (event && event.parse) return event.parse(count)
  } catch (error) {
  }
  return String(event && event.data ? event.data : "").split(",")
}

function isVlcPlaying(players) {
  for (var i = 0; i < (players || []).length; i++) {
    var player = players[i]
    if (!player || !player.isPlaying) continue
    var desktopEntry = String(player.desktopEntry || "").toLowerCase()
    var dbusName = String(player.dbusName || "")
    if (desktopEntry === "vlc" || desktopEntry === "org.videolan.vlc"
        || /^org\.mpris\.MediaPlayer2\.vlc(?:\.|$)/.test(dbusName)) return true
  }
  return false
}

function screensaverWindowsAfter(windows, address, visible) {
  var key = String(address || "")
  if (!key) {
    var current = windows || {}
    var existingCount = 0
    for (var currentKey in current) {
      if (current[currentKey]) existingCount++
    }
    return { windows: current, count: existingCount }
  }

  var next = {}
  var count = 0
  for (var existing in windows || {}) {
    if (existing !== key && windows[existing]) {
      next[existing] = true
      count++
    }
  }

  if (visible) {
    next[key] = true
    count++
  }

  return {
    windows: next,
    count: count
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    secondsFromConfig: secondsFromConfig,
    eventParts: eventParts,
    isVlcPlaying: isVlcPlaying,
    screensaverWindowsAfter: screensaverWindowsAfter
  }
}
