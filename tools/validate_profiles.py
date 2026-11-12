#!/usr/bin/env python3
"""Validate build/profiles/profiles.json against the pinned Kodi version.

Checks
  * guisettings: id exists in Kodi's settings.xml / android.xml for KODI_TAG,
    value type matches, value is an allowed option / inside the range.
    Ids that only exist on Android are reported (they are skipped elsewhere).
  * advancedsettings: only tags known to be read by Kodi 21 (KNOWN_ADVANCED).
  * addons: setting ids exist in the add-on's resources/settings.xml and
    option values are allowed (needs --addons-dir pointing at installed add-ons,
    e.g. a Kodi profile's addons folder; skipped with a warning otherwise).
  * skin: every Skin bool name is referenced somewhere in skin.tonyflix.
Also writes a preview of each profile's advancedsettings.xml to build/profiles/<name>/.

Usage: python3 tools/validate_profiles.py [--addons-dir <kodi>/addons]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "build" / "profiles" / "profiles.json"
SKIN = ROOT / "addons" / "skin.tonyflix"
CACHE = ROOT / ".cache" / "kodi-defs"
KODI_TAG = "21.3-Omega"
DEF_FILES = ("settings.xml", "android.xml")

# Option "fillers" are filled in C++ (xbmc/settings/ServicesSettings.cpp @ 21.3-Omega)
FILLERS = {
    "filecachememorysizes": [16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 0],
    "filecachereadfactors": [0, 110, 125, 150, 175, 200, 250, 300, 400, 500, 700, 1000, 1500, 2000, 3000, 5000],
    "filecachebuffermodes": [0, 1, 2, 3, 4],
    "filecachechunksizes": [256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288],
}
# advancedsettings.xml tags still read by Kodi 21 that TonyFlix may use.
KNOWN_ADVANCED = {"splash", "imageres", "fanartres", "network/curlclienttimeout",
                  "network/curllowspeedtime", "network/curlretries", "loglevel"}


def fetch(url):
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-fsSL", "--max-time", "60", url], capture_output=True)
        if r.returncode == 0:
            return r.stdout
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def kodi_index():
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = {}
    for name in DEF_FILES:
        path = CACHE / f"{KODI_TAG}-{name}"
        if not path.exists():
            path.write_bytes(fetch(f"https://raw.githubusercontent.com/xbmc/xbmc/{KODI_TAG}/system/settings/{name}"))
        plat = "android" if name == "android.xml" else "all"
        for s in ET.parse(path).getroot().iter("setting"):
            sid = s.get("id")
            if not sid:
                continue
            e = idx.setdefault(sid, {"platforms": set()})
            e["platforms"].add(plat)
            if s.get("type"):
                e["type"] = s.get("type")
            opts = s.find("constraints/options")
            if opts is not None:
                vals = [o.text for o in opts.findall("option")]
                e["options"] = vals if vals else FILLERS.get((opts.text or "").strip(), (opts.text or "").strip())
            mn, mx = s.find("constraints/minimum"), s.find("constraints/maximum")
            if mn is not None:
                e["range"] = (int(mn.text), int(mx.text) if mx is not None else None)
    return idx


def check_gui(name, settings, idx, errors, notes):
    for sid, val in settings.items():
        e = idx.get(sid)
        if not e:
            errors.append(f"{name}: guisetting '{sid}' does not exist in Kodi {KODI_TAG}")
            continue
        typ = e.get("type")
        ok_type = {"boolean": isinstance(val, bool), "integer": isinstance(val, int) and not isinstance(val, bool),
                   "string": isinstance(val, str), "addon": isinstance(val, str)}.get(typ, True)
        if not ok_type:
            errors.append(f"{name}: '{sid}' expects {typ}, got {type(val).__name__} {val!r}")
        opts = e.get("options")
        if isinstance(opts, list) and opts and typ == "integer":
            allowed = [int(o) for o in opts]
            if val not in allowed:
                errors.append(f"{name}: '{sid}'={val} not in allowed {allowed}")
        elif isinstance(opts, str) and opts:
            notes.append(f"{name}: '{sid}' uses dynamic options '{opts}' (not checked)")
        if "range" in e:
            lo, hi = e["range"]
            if val < lo or (hi is not None and val > hi):
                errors.append(f"{name}: '{sid}'={val} outside {lo}..{hi}")
        if e["platforms"] == {"android"}:
            notes.append(f"{name}: '{sid}' exists on Android only (skipped on other platforms)")


def flatten(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from flatten(v, key + "/")
        else:
            yield key, v


def advanced_xml(settings):
    root = ET.Element("advancedsettings", version="1.0")

    def add(parent, d):
        for k, v in d.items():
            el = ET.SubElement(parent, k)
            if isinstance(v, dict):
                add(el, v)
            else:
                el.text = str(v)
    add(root, settings)
    ET.indent(root, space="    ")
    return "<!-- Generated by TonyFlix from build/profiles/profiles.json -->\n" + ET.tostring(root, encoding="unicode") + "\n"


def check_addons(name, addons, addons_dir, errors, notes):
    for aid, settings in addons.items():
        sx = addons_dir / aid / "resources" / "settings.xml" if addons_dir else None
        if not sx or not sx.is_file():
            notes.append(f"{name}: cannot check {aid} settings (pass --addons-dir with {aid} installed)")
            continue
        defs = {s.get("id"): s for s in ET.parse(sx).getroot().iter("setting") if s.get("id")}
        for sid, val in settings.items():
            s = defs.get(sid)
            if s is None:
                errors.append(f"{name}: {aid} has no setting '{sid}'")
                continue
            opts = [o.text for o in s.findall("constraints/options/option")]
            if opts and str(val) not in opts:
                errors.append(f"{name}: {aid} '{sid}'={val} not in {opts}")


def check_skin(name, skin, errors):
    text = "\n".join(p.read_text(errors="replace") for p in (SKIN / "1080i").glob("*.xml"))
    for key in ("set_bool", "reset"):
        for b in skin.get(key, []):
            if f"Skin.HasSetting({b})" not in text:
                errors.append(f"{name}: skin bool '{b}' is never read by the skin")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addons-dir", type=Path)
    args = ap.parse_args()
    cfg = json.loads(PROFILES.read_text())
    idx = kodi_index()
    errors, notes = [], []
    for name in ("common", "lite", "standard"):
        p = cfg[name]
        check_gui(name, p.get("guisettings", {}), idx, errors, notes)
        for key, _ in flatten(p.get("advancedsettings", {})):
            if key not in KNOWN_ADVANCED:
                errors.append(f"{name}: advancedsettings tag '{key}' is not in the known Kodi 21 list")
        check_addons(name, p.get("addons", {}), args.addons_dir, errors, notes)
        check_skin(name, p.get("skin", {}), errors)
        if name != "common":
            merged = {**cfg["common"].get("advancedsettings", {}), **p.get("advancedsettings", {})}
            out = PROFILES.parent / name / "advancedsettings.xml"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(advanced_xml(merged))
    for n in sorted(set(notes)):
        print("note:", n)
    for e in errors:
        print("ERROR:", e)
    print(f"{'FAILED' if errors else 'OK'}: {len(errors)} errors, {len(set(notes))} notes "
          f"(Kodi {KODI_TAG} definitions, {len(idx)} settings)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
