#!/usr/bin/env python3
"""Build the TonyFlix Kodi repository into docs/ for GitHub Pages.

For every add-on folder in addons/ this:
  * zips it to docs/<repo>/zips/<id>/<id>-<version>.zip (root folder = add-on id)
  * copies the add-on's icon/fanart next to the zip (Kodi fetches them from there)
  * appends its addon.xml to docs/<repo>/addons.xml and writes addons.xml.md5
Then it writes the family install guide to docs/index.html from build/site/index.html. Kodi's File
Manager can also browse that page as a source, since it links the repository zip.

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
            data = raw_xml.encode("utf-8") if rel.as_posix() == "addon.xml" else path.read_bytes()
            # Fixed timestamp and permissions: the same sources always give byte-identical zips, so
            # rebuilding doesn't change (and re-commit) every zip in docs/.
            info = zipfile.ZipInfo(arc, date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
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


WIZARD_ID = "plugin.program.tonyflix.wizard"
WIZARD_DATA = ADDONS / WIZARD_ID / "resources" / "data"
BUILD_DATA = [  # (source in build/, destination under the wizard's resources/data/)
    ("profiles/profiles.json", "profiles.json"),
    ("addon_defaults/defaults.json", "defaults.json"),
    ("players", "players"),
    ("install.json", "install.json"),
]


def sync_wizard_data(cfg):
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
    add_own_repository(WIZARD_DATA / "install.json", cfg)


def add_own_repository(install_json, cfg):
    """The family installs only the wizard (one zip); the wizard then installs repository.tonyflix
    itself, which keeps the wizard, skin and maintenance service updated."""
    import json
    data = json.loads(install_json.read_text())
    _, version, _, _ = read_addon(ADDONS / "repository.tonyflix", cfg)
    url = f"{cfg['base_url']}/{cfg['repo_subdir']}/zips/repository.tonyflix/repository.tonyflix-{version}.zip"
    data["repositories"] = [r for r in data["repositories"] if r["id"] != "repository.tonyflix"]
    data["repositories"].insert(0, {"id": "repository.tonyflix", "name": "TonyFlix updates", "zip": url})
    install_json.write_text(json.dumps(data, indent=2) + "\n")


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


SITE_TEMPLATE = ROOT / "build" / "site" / "index.html"
REDIRECT_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url={url}"><title>Kodi 21.3 download</title></head>
<body style="font:18px system-ui,sans-serif;background:#0e0e10;color:#ececef;padding:24px">
<p>Starting the Kodi 21.3 download...</p><p><a style="color:#f5a524" href="{url}">Tap here if it doesn't start</a></p>
</body></html>
"""


SETUP_ZIP = "tonyflix-setup.zip"


def write_site(cfg, repo_zip, wizard_zip):
    """docs/index.html = the family install guide (build/site/index.html). Kodi's File Manager also
    browses this page as a source: it lists links whose text is exactly the file name (the repo zip)."""
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    if not repo_zip or not wizard_zip:
        raise SystemExit("the install page needs repository.tonyflix and the wizard")
    # What the family installs: the wizard, under a short, stable name (Kodi only cares about the
    # add-on folder inside the zip). The wizard installs repository.tonyflix itself.
    shutil.copy2(wizard_zip, DOCS / SETUP_ZIP)
    old = DOCS / repo_zip.name
    if old.exists():
        old.unlink()      # the bare repository zip is no longer offered at the top level
    shutil.copy2(ADDONS / "repository.tonyflix" / "icon.png", DOCS / "icon.png")
    downloads = cfg.get("kodi_downloads", {})
    for name, url in downloads.items():   # short addresses to type into the Downloader app
        (DOCS / name).mkdir(exist_ok=True)
        (DOCS / name / "index.html").write_text(REDIRECT_PAGE.format(url=html.escape(url, quote=True)),
                                                 encoding="utf-8")
    tokens = {
        "BUILD_NAME": cfg["build_name"],
        "BUILD_NAME_UPPER": cfg["build_name"].upper(),
        "BASE_URL": cfg["base_url"],
        "SETUP_ZIP": SETUP_ZIP,
        "KODI64_URL": downloads.get("kodi64", "https://kodi.tv/download/android/"),
        "KODI32_URL": downloads.get("kodi32", "https://kodi.tv/download/android/"),
    }
    page = SITE_TEMPLATE.read_text(encoding="utf-8")
    for key, value in tokens.items():
        page = page.replace("{{" + key + "}}", html.escape(value, quote=True))
    if "{{" in page:
        raise SystemExit(f"unfilled token in {SITE_TEMPLATE}: {page[page.index('{{'):][:40]}")
    (DOCS / "index.html").write_text(page, encoding="utf-8")


def main():
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
    sync_wizard_data(cfg)
    repo = DOCS / cfg["repo_subdir"]
    if args.clean and repo.exists():
        shutil.rmtree(repo)
    zips_root = repo / "zips"

    entries, repo_zip, wizard_zip = [], None, None
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
        if addon_id == WIZARD_ID:
            wizard_zip = zpath
        size_mb = zpath.stat().st_size / 1_048_576
        print(f"  {addon_id} {version}  ({size_mb:.1f} MB)")

    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    addons_xml += "\n".join(entries) + "\n</addons>\n"
    (repo / "addons.xml").write_text(addons_xml, encoding="utf-8")
    (repo / "addons.xml.md5").write_text(hashlib.md5(addons_xml.encode("utf-8")).hexdigest())

    write_site(cfg, repo_zip, wizard_zip)
    shown = repo.relative_to(ROOT) if repo.is_relative_to(ROOT) else repo
    print(f"Repo written to {shown}  (base_url: {cfg['base_url']})")


if __name__ == "__main__":
    main()
