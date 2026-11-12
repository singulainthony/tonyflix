#!/usr/bin/env python3
"""One-time import of Arctic Horizon 2 into addons/skin.tonyflix.

Copies the upstream skin, deletes everything a movies/TV-only build never
shows (PVR, music, games, pictures, weather, non-English languages), and
rewrites addon.xml with the TonyFlix id. After this runs, addons/skin.tonyflix
is our own source and gets edited directly; this script is kept as a record of
what was removed. NOTE: hand edits made after import (menus, overrides,
texture optimisation) are NOT reproduced by re-running it.

Upstream: https://github.com/jurialmunkey/skin.arctic.horizon.2 (archived 2024-10-09)
          Use the `omega` branch (Kodi 21 / xbmc.gui 5.17.0); `main` is the Kodi 20 build.
License:  CC BY-NC-SA 4.0 (design portions). Credit kept in addon.xml + CREDITS.md.

Usage: python3 tools/import_upstream.py <path to skin.arctic.horizon.2 checkout> [--force]
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "addons" / "skin.tonyflix"

REMOVE_WINDOWS = [
    # Live TV / PVR
    "DialogPVRChannelGuide", "DialogPVRChannelManager", "DialogPVRChannelsOSD",
    "DialogPVRGroupManager", "DialogPVRGuideSearch", "DialogPVRInfo",
    "MyPVRChannels", "MyPVRGuide", "MyPVRRecordings", "MyPVRSearch", "MyPVRTimers",
    # Music
    "DialogMusicInfo", "MusicOSD", "MusicVisualisation", "MyMusicNav", "MyMusicPlaylistEditor",
    "Custom_1142_OSD_MusicTracks", "Custom_1196_AutoVis", "script-cu-lrclyrics-main",
    # Games
    "MyGames", "GameOSD", "DialogGameControllers", "Custom_1151_GameOptions",
    # Pictures
    "MyPics", "SlideShow", "DialogPictureInfo",
    # Weather
    "MyWeather",
    # Kodi-library hubs (TonyFlix has no library; TMDb hubs 1120/1121 are used)
    "Custom_1130_Hub_Library_Movies", "Custom_1131_Hub_Library_TVShows",
    # Heavy animated screensaver (Kodi's built-in Dim is used instead)
    "screensaver-arctic-mirage",
]
REMOVE_INCLUDE_FILES = ["Includes_Views_PVR", "Includes_Weather"]  # only used by removed windows
REMOVE_PATHS = [
    # NB: media/pvr stays — its progress-bar textures are reused by episode/OSD layouts.
    # NB: extras/screenshots stays — used by the background-style picker (downscaled instead).
    "extras/backgrounds/music_colors",
    "media/weather",
    "shortcuts/livetv-1.DATA.xml",
    "shortcuts/music-1.DATA.xml",
]
KEEP_LANGUAGES = {"resource.language.en_gb"}

ADDON_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="skin.tonyflix" name="TonyFlix" provider-name="TonyFlix (based on Arctic Horizon 2 by jurialmunkey)" version="1.0.0">
    <requires>
        <import addon="xbmc.gui" version="5.17.0" />
        <import addon="script.skinshortcuts" version="0.4.0" />
        <import addon="script.skinvariables" version="1.0.0" />
        <import addon="script.texturemaker" version="0.2.8" />
        <import addon="plugin.video.themoviedb.helper" version="6.20.5" />
        <!-- TMDbHelper 6.x moved Trakt into a separate sync-provider module; Trakt rows need it -->
        <import addon="script.module.tmdbhelper.sync.trakt" version="1.2.9" />
        <import addon="resource.images.studios.coloured" version="0.0.1" />
        <import addon="resource.font.robotocjksc" version="0.0.1" />
    </requires>
    <extension debugging="false" defaultthemename="Textures.xbt" effectslowdown="0.75" point="xbmc.gui.skin">
        <res aspect="16:9" default="true" folder="1080i" height="1080" width="1920" />
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="en_GB">Fast, Netflix-style movies and TV for low-power boxes.</summary>
        <description lang="en_GB">TonyFlix is a trimmed fork of Arctic Horizon 2 by jurialmunkey, tuned for weak Android TV boxes. Movies and TV shows only.</description>
        <disclaimer lang="en_GB">Based on Arctic Horizon 2 by jurialmunkey. Licensed CC BY-NC-SA 4.0. Not for commercial use.</disclaimer>
        <platform>all</platform>
        <license>CC-BY-NC-SA-4.0</license>
        <source>https://github.com/jurialmunkey/skin.arctic.horizon.2</source>
        <assets>
            <icon>icon.png</icon>
            <fanart>fanart.jpg</fanart>
        </assets>
    </extension>
</addon>
"""

CREDITS = """# Credits

TonyFlix skin is a modified fork of **Arctic Horizon 2** by **jurialmunkey**
(https://github.com/jurialmunkey/skin.arctic.horizon.2, upstream commit
{commit}, archived 2024-10-09).

The design portions are licensed under the Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 license (see LICENSE.txt). This fork
is distributed under the same license: non-commercial use only, with credit to
the original author, and modifications shared under the same terms.

Modifications in TonyFlix: removed Live TV/PVR, music, games, pictures and
weather windows; removed non-English languages; downscaled large textures and
preview images; performance-oriented defaults for low-power Android devices.

Background photos in extras/backgrounds/launch are from Unsplash (Unsplash
License) as shipped with the original skin.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream", type=Path)
    ap.add_argument("--force", action="store_true", help="overwrite an existing addons/skin.tonyflix")
    ap.add_argument("--commit", default="unknown")
    args = ap.parse_args()

    src = args.upstream.resolve()
    if not (src / "addon.xml").is_file() or 'id="skin.arctic.horizon.2"' not in (src / "addon.xml").read_text():
        sys.exit(f"{src} is not an Arctic Horizon 2 checkout")
    if DEST.exists():
        if not args.force:
            sys.exit(f"{DEST} already exists (use --force to overwrite)")
        shutil.rmtree(DEST)

    shutil.copytree(src, DEST, ignore=shutil.ignore_patterns(".git", ".github", ".gitignore", "*.psd"))

    removed = 0
    for name in REMOVE_WINDOWS + REMOVE_INCLUDE_FILES:
        f = DEST / "1080i" / f"{name}.xml"
        if f.exists():
            f.unlink()
            removed += 1
        else:
            print(f"  (not found: {f.name})")
    inc = DEST / "1080i" / "Includes.xml"
    text = inc.read_text(encoding="utf-8")
    for name in REMOVE_INCLUDE_FILES:
        text = text.replace(f'    <include file="{name}.xml" />\n', "")
    inc.write_text(text, encoding="utf-8")

    for rel in REMOVE_PATHS:
        p = DEST / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        removed += 1
    for lang in (DEST / "language").iterdir():
        if lang.name not in KEEP_LANGUAGES:
            shutil.rmtree(lang)
            removed += 1

    (DEST / "addon.xml").write_text(ADDON_XML, encoding="utf-8")
    (DEST / "CREDITS.md").write_text(CREDITS.format(commit=args.commit), encoding="utf-8")
    (DEST / "Readme.md").unlink(missing_ok=True)
    print(f"Imported to {DEST.relative_to(ROOT)}; removed {removed} files/folders.")


if __name__ == "__main__":
    main()
