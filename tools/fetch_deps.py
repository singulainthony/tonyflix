#!/usr/bin/env python3
"""Resolve and download Kodi add-on dependencies from their official repos.

Dev/test helper: lets us install the TonyFlix skin plus everything it needs
into a throwaway Kodi profile without clicking through Kodi's installer. (On
real devices the wizard asks Kodi itself to install from these same repos.)

Walks <requires><import> recursively (skipping xbmc.* and optional imports),
picks the highest version across all repos like Kodi does, downloads each zip
from its repo's datadir and extracts it into --dest.

Usage:
  python3 tools/fetch_deps.py --dest <kodi>/addons --cache <dir> \
      [--local addons/skin.tonyflix ...] [--extra repository.jurialmunkey ...] [ids...]
"""
import argparse
import gzip
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# Kodi 21 "Omega". Order matters only for tie-breaking equal versions.
REPOS = [
    ("jurialmunkey-omega", "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips/"),
    ("jurialmunkey", "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/repo/zips/"),
    ("kodi-official-omega", "https://mirrors.kodi.tv/addons/omega/"),
]
UA = {"User-Agent": "Kodi-dependency-fetcher/1.0"}
# Provided by Kodi itself (built-in binary/python modules), never downloaded.
BUILTIN = re.compile(r"^(xbmc\.|kodi\.|script\.module\.pil$)")


def vkey(v):
    """Kodi-ish version ordering: numeric parts, then '~tag' sorts before no tag."""
    main, _, tag = v.partition("~")
    nums = [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", main)]
    return (nums + [0] * (6 - len(nums)), 0 if tag else 1, tag)


def fetch(url):
    # Prefer curl: python.org builds on macOS often ship without CA certificates.
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-fsSL", "--max-time", "120", "-A", UA["User-Agent"], url], capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"curl {url}: {r.stderr.decode().strip()}")
        return r.stdout
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def load_index(base):
    errors = []
    for name in ("addons.xml", "addons.xml.gz"):
        try:
            data = fetch(base + name)
        except Exception as e:
            errors.append(str(e))
            continue
        if name.endswith(".gz"):
            data = gzip.decompress(data)
        return ET.fromstring(data)
    raise RuntimeError(f"no addons.xml at {base}: {'; '.join(errors)}")


def requires(addon_el):
    req = addon_el.find("requires")
    if req is None:
        return []
    return [i.get("addon") for i in req.findall("import") if i.get("optional", "false") != "true"]


def safe_extract(zpath, dest, addon_id):
    """Extract a repo zip to dest/<addon_id> (Kodi names the folder by id, even when
    the zip's root folder is spelled differently)."""
    tmp = dest / f".tmp-{addon_id}"
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(zpath) as zf:
        for m in zf.namelist():
            target = (tmp / m).resolve()
            if not str(target).startswith(str(tmp.resolve()) + "/"):
                raise RuntimeError(f"unsafe path in {zpath.name}: {m}")
        roots = {m.split("/")[0] for m in zf.namelist()}
        if len(roots) != 1:
            raise RuntimeError(f"{zpath.name}: expected one root folder, got {sorted(roots)}")
        zf.extractall(tmp)
    final = dest / addon_id
    if final.exists():
        shutil.rmtree(final)
    (tmp / roots.pop()).rename(final)
    shutil.rmtree(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--local", type=Path, nargs="*", default=[], help="local add-on folders to install + resolve")
    ap.add_argument("--extra", nargs="*", default=[], help="extra add-on ids to install")
    args = ap.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    catalog = {}  # id -> (version, base_url, element)
    for name, base in REPOS:
        root = load_index(base)
        n = 0
        for a in root.findall("addon"):
            aid, ver = a.get("id"), a.get("version")
            if aid not in catalog or vkey(ver) > vkey(catalog[aid][0]):
                catalog[aid] = (ver, base, a)
            n += 1
        print(f"  index {name}: {n} add-ons")

    todo = list(args.ids) + list(args.extra)
    for folder in args.local:
        el = ET.parse(folder / "addon.xml").getroot()
        todo += requires(el)
        dst = args.dest / folder.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(folder, dst)
        print(f"  local  {folder.name} {el.get('version')}")

    seen, missing = set(), []
    while todo:
        aid = todo.pop()
        if aid in seen or BUILTIN.match(aid):
            continue
        seen.add(aid)
        if aid not in catalog:
            missing.append(aid)
            continue
        ver, base, el = catalog[aid]
        zname = f"{aid}-{ver}.zip"
        zpath = args.cache / zname
        if not zpath.exists():
            zpath.write_bytes(fetch(f"{base}{aid}/{zname}"))
        safe_extract(zpath, args.dest, aid)
        print(f"  remote {aid} {ver}  <- {base.split('/')[2]}")
        todo += requires(el)

    if missing:
        print("MISSING (not in any repo):", ", ".join(sorted(missing)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
