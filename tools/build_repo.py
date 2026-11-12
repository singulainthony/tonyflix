#!/usr/bin/env python3
"""Build the TonyFlix Kodi repository into docs/ for GitHub Pages.

For every add-on folder in addons/ this:
  * zips it to docs/<repo>/zips/<id>/<id>-<version>.zip (root folder = add-on id)
  * copies the add-on's icon/fanart next to the zip (Kodi fetches them from there)
  * appends its addon.xml to docs/<repo>/addons.xml and writes addons.xml.md5
Then it writes docs/index.html (browsable from Kodi's File Manager as a source)
with a link to the repository zip.

Placeholders {BASE_URL} and {REPO_SUBDIR} in any addon.xml are replaced in the
zipped copy from tools/config.json, so the source tree stays URL-agnostic.

Usage: python3 tools/build_repo.py [--clean]
"""
import argparse
import fnmatch
import hashlib
import html
import json
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDONS = ROOT / "addons"
DOCS = ROOT / "docs"


def load_config():
    cfg = json.loads((ROOT / "tools" / "config.json").read_text())
    cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


def fill(text, cfg):
    return text.replace("{BASE_URL}", cfg["base_url"]).replace("{REPO_SUBDIR}", cfg["repo_subdir"])


def excluded(rel, patterns):
    return any(fnmatch.fnmatch(part, pat) for part in rel.parts for pat in patterns)


def read_addon(folder, cfg):
    raw = fill((folder / "addon.xml").read_text(encoding="utf-8"), cfg)
    root = ET.fromstring(raw.encode("utf-8"))
    if root.tag != "addon":
        raise ValueError(f"{folder}/addon.xml: root element is not <addon>")
    addon_id, version = root.get("id"), root.get("version")
    if addon_id != folder.name:
        raise ValueError(f"{folder}: folder name must equal add-on id '{addon_id}'")
    assets = []
    for ext in root.iter("extension"):
        if ext.get("point") == "xbmc.addon.metadata":
            for tag in ("icon", "fanart"):
                for el in ext.iter(tag):
                    if el.text:
                        assets.append(el.text.strip())
    return addon_id, version, raw, assets


def zip_addon(folder, addon_id, version, raw_xml, out_dir, cfg):
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"{addon_id}-{version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(folder.rglob("*")):
            rel = path.relative_to(folder)
            if path.is_dir() or excluded(rel, cfg["zip_exclude"]):
                continue
            arc = f"{addon_id}/{rel.as_posix()}"
            if rel.as_posix() == "addon.xml":
                zf.writestr(arc, raw_xml)
            else:
                zf.write(path, arc)
    # repository.tonyflix uses <hashes>sha256</hashes>: Kodi fetches <zip>.sha256 and
    # refuses the install if it is missing or doesn't match.
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    (out_dir / f"{zpath.name}.sha256").write_text(f"{digest}  {zpath.name}\n")
    return zpath


def addon_xml_body(raw):
    """addon.xml without the XML declaration and comments, for addons.xml."""
    root = ET.fromstring(raw.encode("utf-8"))
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode")


WIZARD_DATA = ADDONS / "plugin.program.tonyflix.wizard" / "resources" / "data"
BUILD_DATA = [  # (source in build/, destination under the wizard's resources/data/)
    ("profiles/profiles.json", "profiles.json"),
    ("addon_defaults/defaults.json", "defaults.json"),
    ("players", "players"),
    ("install.json", "install.json"),
]


def sync_wizard_data():
    """Copy build/ data (single source of truth) into the wizard add-on."""
    if not WIZARD_DATA.parent.parent.exists():
        return
    for src, dst in BUILD_DATA:
        s, d = ROOT / "build" / src, WIZARD_DATA / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    add_skin_requires(WIZARD_DATA / "install.json")


def add_skin_requires(install_json):
    """Record the skin's add-on dependencies in the wizard's install.json, so the wizard can install
    them one at a time before the skin (Kodi's own dependency pass can miss one while it is still
    re-reading repositories)."""
    import json
    import xml.etree.ElementTree as ET
    data = json.loads(install_json.read_text())
    skin_xml = ROOT / "addons" / data["skin"]["id"] / "addon.xml"
    req = [i.get("addon") for i in ET.parse(skin_xml).getroot().iter("import")
           if not i.get("addon").startswith(("xbmc.", "kodi.")) and i.get("optional") != "true"]
    data["skin"]["requires"] = req
    install_json.write_text(json.dumps(data, indent=2) + "\n")


def main():
    sync_wizard_data()
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="delete the repo output first")
    ap.add_argument("--base-url", help="override base_url (e.g. http://127.0.0.1:8099 for local testing)")
    ap.add_argument("--out", type=Path, help="write the site here instead of docs/")
    args = ap.parse_args()
    cfg = load_config()
    if args.base_url:
        cfg["base_url"] = args.base_url.rstrip("/")
    global DOCS
    if args.out:
        DOCS = args.out.resolve()
    repo = DOCS / cfg["repo_subdir"]
    if args.clean and repo.exists():
        shutil.rmtree(repo)
    zips_root = repo / "zips"

    entries, repo_zip = [], None
    folders = sorted(p for p in ADDONS.iterdir() if (p / "addon.xml").is_file())
    if not folders:
        sys.exit("No add-ons found in addons/")
    for folder in folders:
        addon_id, version, raw, assets = read_addon(folder, cfg)
        out_dir = zips_root / addon_id
        zpath = zip_addon(folder, addon_id, version, raw, out_dir, cfg)
        for asset in assets:
            src = folder / asset
            if src.is_file():
                dst = out_dir / asset
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            else:
                print(f"  ! {addon_id}: missing asset {asset}")
        entries.append(addon_xml_body(raw))
        if addon_id.startswith("repository."):
            repo_zip = zpath
        size_mb = zpath.stat().st_size / 1_048_576
        print(f"  {addon_id} {version}  ({size_mb:.1f} MB)")

    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    addons_xml += "\n".join(entries) + "\n</addons>\n"
    (repo / "addons.xml").write_text(addons_xml, encoding="utf-8")
    (repo / "addons.xml.md5").write_text(hashlib.md5(addons_xml.encode("utf-8")).hexdigest())

    # Landing page: Kodi's File Manager can browse this as an HTTP source.
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    links = ""
    if repo_zip:
        rel = repo_zip.relative_to(DOCS).as_posix()
        name = html.escape(repo_zip.name)
        shutil.copy2(repo_zip, DOCS / repo_zip.name)  # top-level copy = short path in Kodi
        links = f'<a href="{name}">{name}</a><br>\n<a href="{rel}">{rel}</a>\n'
    (DOCS / "index.html").write_text(
        f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{html.escape(cfg['build_name'])}</title>"
        f"</head><body>\n{links}</body></html>\n",
        encoding="utf-8",
    )
    shown = repo.relative_to(ROOT) if repo.is_relative_to(ROOT) else repo
    print(f"Repo written to {shown}  (base_url: {cfg['base_url']})")


if __name__ == "__main__":
    main()
