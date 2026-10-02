import json
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for the idle model tests")
class IdlePlaybackTests(unittest.TestCase):
    def check_playback(self, players, expected):
        model = Path(__file__).resolve().parents[1] / "screensaver/cph.idle/IdleModel.js"
        result = subprocess.run(
            ["node", "-e", "const model = require(process.argv[1]); "
             "console.log(JSON.stringify(model.isVlcPlaying(JSON.parse(process.argv[2]))));",
             str(model), json.dumps(players)],
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), expected)

    def test_vlc_playback_inhibits_idle_for_native_and_flatpak_players(self):
        for player in [
            {"desktopEntry": "vlc", "isPlaying": True},
            {"desktopEntry": "org.videolan.VLC", "isPlaying": True},
            {"dbusName": "org.mpris.MediaPlayer2.vlc", "isPlaying": True},
            {"dbusName": "org.mpris.MediaPlayer2.vlc.instance42", "isPlaying": True},
        ]:
            with self.subTest(player=player):
                self.check_playback([player], True)

    def test_paused_stopped_and_closed_vlc_allow_idle(self):
        for players in [[], None, [{"desktopEntry": "vlc", "isPlaying": False}],
                        [{"dbusName": "org.mpris.MediaPlayer2.vlc.instance42", "isPlaying": False}]]:
            with self.subTest(players=players):
                self.check_playback(players, False)

    def test_other_players_do_not_disable_idle(self):
        self.check_playback([
            None, {"desktopEntry": "firefox", "isPlaying": True},
            {"dbusName": "org.mpris.MediaPlayer2.vlc-imposter", "isPlaying": True},
        ], False)

    def test_one_playing_vlc_instance_inhibits_idle_among_paused_players(self):
        self.check_playback([
            {"desktopEntry": "vlc", "isPlaying": False},
            {"desktopEntry": "firefox", "isPlaying": True},
            {"dbusName": "org.mpris.MediaPlayer2.vlc.instance42", "isPlaying": True},
        ], True)
