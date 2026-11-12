#!/usr/bin/env python3
"""Static checker for a Kodi skin folder.

Catches the breakage that trimming a skin causes, without launching Kodi:
  * XML files that fail to parse
  * <include>Name</include> / content="Name" with no matching <include name=..>
  * $VAR[Name] / $EXP[Name] with no matching <variable>/<expression>
  * <include file="X.xml"> pointing at a missing file
  * skin textures (media/..., special://skin/...) that no longer exist

Includes generated at runtime by script.skinshortcuts / script.skinvariables
(and referenced by prefix) are treated as external.

Usage: python3 tools/check_skin.py <skin folder> [--baseline file] [--write-baseline file]
A baseline lets you ignore problems that already existed upstream.
Exit code 1 if there are problems not in the baseline.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

GENERATED_FILES = {"script-skinshortcuts-includes.xml", "script-skinviewtypes-includes.xml"}
EXTERNAL_PREFIXES = ("skinshortcuts-", "skinvariables-", "skinviewtypes-")
TEXTURE_TAGS = {
    "texture", "texturefocus", "texturenofocus", "alttexturefocus", "alttexturenofocus",
    "texturesliderbar", "texturesliderbackground", "texturesliderbarfocus", "textureslidernib",
    "textureslidernibfocus", "textureup", "texturedown", "textureupfocus", "texturedownfocus",
    "textureleft", "textureright", "textureleftfocus", "texturerightfocus", "texturebg",
    "midtexture", "lefttexture", "righttexture", "overlaytexture", "imagepath", "bordertexture",
    "texturecheck", "texturecheckfocus", "texturechecknofocus", "textureradioonfocus",
    "textureradioonnofocus", "textureradioofffocus", "textureradiooffnofocus",
}
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
VAR_RE = re.compile(r"\$VAR\[([^\]\[,$]+)\]")
EXP_RE = re.compile(r"\$EXP\[([^\]\[,$]+)\]")
SKIN_PATH_RE = re.compile(r"special://skin/([^\"'<>\s\],|$]+)")


def is_external(name):
    return name.startswith(EXTERNAL_PREFIXES)


def scan(skin):
    xml_dir = skin / "1080i"
    media = skin / "media"
    defined = {"include": set(), "variable": set(), "expression": set()}
    used = []  # (kind, name, file)
    problems = []
    texts = {}

    for f in sorted(xml_dir.glob("*.xml")):
        text = f.read_text(encoding="utf-8", errors="replace")
        texts[f.name] = text
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as e:
            problems.append(f"parse-error {f.name}: {e}")
            continue
        for el in root.iter():
            name = el.get("name")
            if el.tag == "include":
                if name and len(el) + len((el.text or "").strip()) >= 0 and el.get("content") is None and (
                    el.find("*") is not None or not (el.text or "").strip()
                ):
                    defined["include"].add(name)
                if el.get("file"):
                    if el.get("file") not in GENERATED_FILES and not (xml_dir / el.get("file")).is_file():
                        problems.append(f"missing-include-file {f.name}: {el.get('file')}")
                    continue
                ref = el.get("content") or ((el.text or "").strip() if el.find("*") is None and not name else None)
                if ref and "$" not in ref:
                    used.append(("include", ref, f.name))
            elif el.tag == "variable" and name:
                defined["variable"].add(name)
            elif el.tag == "expression" and name:
                defined["expression"].add(name)
            if el.tag in TEXTURE_TAGS and el.text:
                tex = el.text.strip()
                if tex and "$" not in tex and "://" not in tex and tex.lower().endswith(IMG_EXT):
                    if not (media / tex).is_file():
                        problems.append(f"missing-texture {f.name}: {tex}")

        for m in VAR_RE.finditer(text):
            used.append(("variable", m.group(1).strip(), f.name))
        for m in EXP_RE.finditer(text):
            used.append(("expression", m.group(1).strip(), f.name))

    # skinshortcuts template.xml is turned into script-skinshortcuts-includes.xml at
    # runtime, so the includes it references must exist in the skin too.
    template = skin / "shortcuts" / "template.xml"
    if template.is_file():
        try:
            troot = ET.fromstring(template.read_bytes())
            for el in troot.iter("include"):
                ref = el.get("content") or ((el.text or "").strip() if el.find("*") is None and not el.get("name") else None)
                if ref and "$" not in ref:
                    used.append(("include", ref, "shortcuts/template.xml"))
        except ET.ParseError as e:
            problems.append(f"parse-error shortcuts/template.xml: {e}")

    # special://skin/ references across xml, shortcuts and colors
    for f in list(xml_dir.glob("*.xml")) + list((skin / "shortcuts").glob("*")) + list((skin / "colors").glob("*")):
        if not f.is_file():
            continue
        for m in SKIN_PATH_RE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            rel = m.group(1).rstrip("/.)")
            if "$" in rel or "{" in rel or not rel.lower().endswith(IMG_EXT + (".xml", ".json", ".ttf")):
                continue
            if not (skin / rel).exists():
                problems.append(f"missing-skin-file {f.name}: special://skin/{rel}")

    for kind, name, fname in used:
        if is_external(name):
            continue
        if name not in defined[kind]:
            problems.append(f"undefined-{kind} {fname}: {name}")

    return sorted(set(problems)), defined


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skin", type=Path)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--write-baseline", type=Path)
    args = ap.parse_args()

    problems, defined = scan(args.skin)
    if args.write_baseline:
        args.write_baseline.write_text("\n".join(problems) + "\n")
        print(f"Baseline: {len(problems)} pre-existing problems written to {args.write_baseline}")
        return 0
    base = set()
    if args.baseline and args.baseline.is_file():
        # Baseline entries are matched without the file name, so a problem that
        # moves between files (or is shared by several) still counts as known.
        base = {p.split(" ", 1)[0] + " " + p.split(": ", 1)[-1] for p in args.baseline.read_text().splitlines() if p}
    new = [p for p in problems if (p.split(" ", 1)[0] + " " + p.split(": ", 1)[-1]) not in base]
    print(
        f"Defined: {len(defined['include'])} includes, {len(defined['variable'])} variables, "
        f"{len(defined['expression'])} expressions. Problems: {len(problems)} total, {len(new)} new."
    )
    for p in new:
        print("  " + p)
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
