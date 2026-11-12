#!/usr/bin/env python3
"""Offline tests for the wizard's profile module (no Kodi needed).

Stubs the xbmc* modules, then checks:
  * suggest_profile() on real-world box specs (T95 Max H6, T95 Max+ S905X3, Shield, Fire TV 4K Max)
  * apply_skin() file mode (TonyFlix not the active skin yet): sets/resets bools in
    addon_data/skin.tonyflix/settings.xml without duplicating entries.
Usage: python3 tools/test_wizard_profiles.py
"""
import json
import sys
import tempfile
import types
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIZ = ROOT / "addons" / "plugin.program.tonyflix.wizard"
TMP = Path(tempfile.mkdtemp())


def stub_modules():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.log = lambda *a, **k: None
    xbmc.getInfoLabel = lambda label: ""
    xbmc.getCondVisibility = lambda cond: False
    xbmc.getSkinDir = lambda: "skin.estuary"
    xbmc.sleep = lambda ms: None
    xbmc.executebuiltin = lambda *a: None
    xbmcaddon = types.ModuleType("xbmcaddon")

    class Addon:
        def __init__(self, aid=None):
            pass

        def getAddonInfo(self, key):
            return {"path": str(WIZ), "profile": str(TMP / "addon_data" / "plugin.program.tonyflix.wizard")}[key]
    xbmcaddon.Addon = Addon
    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda p: str(TMP) + "/" if p == "special://profile/" else p
    sys.modules.update(xbmc=xbmc, xbmcaddon=xbmcaddon, xbmcvfs=xbmcvfs)


def main():
    stub_modules()
    sys.path.insert(0, str(WIZ / "resources" / "lib"))
    from tonyflix import profiles
    rules = json.loads((ROOT / "build" / "profiles" / "profiles.json").read_text())["detection"]
    boxes = {
        "T95 Max (H6, 4 GB, 64-bit)": ({"ram_mb": 3800, "cpu_cores": 4, "kodi_64bit": True, "gpu": "Mali-T720", "soc": "sun50iw6"}, "lite"),
        "T95 Max (fake-4GB, 32-bit Kodi)": ({"ram_mb": 1900, "cpu_cores": 4, "kodi_64bit": False, "gpu": "", "soc": ""}, "lite"),
        "T95 Max+ (S905X3, 4 GB)": ({"ram_mb": 3700, "cpu_cores": 4, "kodi_64bit": True, "gpu": "Mali-G31", "soc": "sm1"}, "lite"),
        "Nvidia Shield 2019 Pro (3 GB)": ({"ram_mb": 2900, "cpu_cores": 4, "kodi_64bit": True, "gpu": "NVIDIA Tegra X1", "soc": ""}, "standard"),
        "Generic 2 GB box": ({"ram_mb": 1950, "cpu_cores": 4, "kodi_64bit": True, "gpu": "Mali-G52", "soc": ""}, "lite"),
        "Fire TV Stick 4K Max (2nd gen)": ({"ram_mb": 3800, "cpu_cores": 4, "kodi_64bit": True, "gpu": "Mali-G52", "soc": "mt8696"}, "standard"),
        "Desktop / Mac": ({"ram_mb": 16384, "cpu_cores": 8, "kodi_64bit": True, "gpu": "Apple M1", "soc": ""}, "standard"),
    }
    fails = 0
    for label, (hw, want) in boxes.items():
        got, reasons = profiles.suggest_profile(hw, rules)
        ok = got == want
        fails += not ok
        print(f"{'ok ' if ok else 'BAD'} {label:34s} -> {got:8s} {reasons}")

    # apply_skin in file mode, twice (second call must not duplicate entries)
    report = {}
    path = TMP / "addon_data" / "skin.tonyflix" / "settings.xml"
    path.parent.mkdir(parents=True)
    path.write_text('<settings version="2"><setting id="SelectBox.Glow" type="bool">true</setting>'
                    '<setting id="ForegroundStyle" type="string">FlixArt</setting></settings>')
    for _ in range(2):
        profiles.apply_skin(["TonyFlix.Lite", "Textboxes.DisableAutoscroll"], ["SelectBox.Glow"], report)
    ids = [s.get("id") for s in ET.parse(path).getroot().findall("setting")]
    checks = {
        "file mode used": report.get("skin_mode", "").startswith("settings file"),
        "Lite set once": ids.count("TonyFlix.Lite") == 1,
        "Glow removed": "SelectBox.Glow" not in ids,
        "other settings kept": "ForegroundStyle" in ids,
    }
    for k, v in checks.items():
        fails += not v
        print(f"{'ok ' if v else 'BAD'} skin file: {k}")
    print("FAILED" if fails else "ALL PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
