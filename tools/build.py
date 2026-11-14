#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Splits the LaunchBox Games Database's Metadata.xml into small cover files.

    python -I tools/build.py                 # downloads Metadata.zip, rewrites data/
    python -I tools/build.py --zip PATH      # uses a Metadata.zip already on disk

Only what a frontend needs to find a box cover is kept: per platform, per first letter of a
normalised title, the games with that key and their front cover file per region. Beside them, in
files of their own, the other faces of each game's box, cartridge and disc (FACE_TYPES), for
frontends that draw the game as an object. Images stay on LaunchBox's own server
(images.launchbox-app.com); nothing here is an image.
"""

import argparse
import datetime
import email.utils
import json
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

SOURCE = "https://gamesdb.launchbox-app.com/Metadata.zip"
IMAGES = "https://images.launchbox-app.com/"
FORMAT = 1
# Front covers, best first. A game gets the first kind it has, one file per region.
COVER_TYPES = ["Box - Front", "Box - Front - Reconstructed", "Fanart - Box - Front"]
# The other faces, by the name the face files give them, best kind first.
FACE_TYPES = {
    "back": ["Box - Back", "Box - Back - Reconstructed", "Fanart - Box - Back"],
    "spine": ["Box - Spine"],
    "cart": ["Cart - Front", "Fanart - Cart - Front"],
    "cart_back": ["Cart - Back", "Fanart - Cart - Back"],
    "disc": ["Disc", "Fanart - Disc"],
}
IMAGE_TYPES = set(COVER_TYPES) | {kind for kinds in FACE_TYPES.values() for kind in kinds}
ROOT = Path(__file__).resolve().parent.parent

# Latin-1 letters with accents, as the plain letters they stand for. Frontends that match
# against these keys must use the same table (see README, "Keys").
ACCENTS = {
    "a": "àáâãäåā", "c": "çćč", "e": "èéêëēėę", "i": "ìíîïī", "n": "ñń", "o": "òóôõöøō",
    "u": "ùúûüū", "y": "ýÿ", "s": "śšß", "z": "źżž", "l": "ł", "ae": "æ", "oe": "œ",
}
FOLD = {ch: plain for plain, chars in ACCENTS.items() for ch in chars}

# libretro thumbnail folders (No-Intro / Redump system names) that name a LaunchBox platform,
# so a frontend that already knows those names needs no table of its own.
LIBRETRO = {
    "Atari - 2600": "Atari 2600", "Atari - 5200": "Atari 5200", "Atari - 7800": "Atari 7800",
    "Atari - Jaguar": "Atari Jaguar", "Atari - Lynx": "Atari Lynx",
    "Bandai - WonderSwan": "WonderSwan", "Bandai - WonderSwan Color": "WonderSwan Color",
    "FBNeo - Arcade Games": "Arcade", "MAME": "Arcade", "GCE - Vectrex": "GCE Vectrex",
    "Microsoft - MSX": "Microsoft MSX", "Microsoft - MSX2": "Microsoft MSX2",
    "NEC - PC Engine - TurboGrafx 16": "NEC TurboGrafx-16",
    "NEC - PC Engine CD - TurboGrafx-CD": "NEC TurboGrafx-CD",
    "Nintendo - Game Boy": "Nintendo Game Boy", "Nintendo - Game Boy Advance": "Nintendo Game Boy Advance",
    "Nintendo - Game Boy Color": "Nintendo Game Boy Color", "Nintendo - GameCube": "Nintendo GameCube",
    "Nintendo - Nintendo 3DS": "Nintendo 3DS", "Nintendo - Nintendo 64": "Nintendo 64",
    "Nintendo - Nintendo DS": "Nintendo DS",
    "Nintendo - Nintendo Entertainment System": "Nintendo Entertainment System",
    "Nintendo - Family Computer Disk System": "Nintendo Famicom Disk System",
    "Nintendo - Pokemon Mini": "Nintendo Pokemon Mini",
    "Nintendo - Super Nintendo Entertainment System": "Super Nintendo Entertainment System",
    "Nintendo - Virtual Boy": "Nintendo Virtual Boy", "Nintendo - Wii": "Nintendo Wii",
    "Nintendo - Wii U": "Nintendo Wii U",
    "SNK - Neo Geo Pocket": "SNK Neo Geo Pocket", "SNK - Neo Geo Pocket Color": "SNK Neo Geo Pocket Color",
    "SNK - Neo Geo CD": "SNK Neo Geo CD",
    "Sega - 32X": "Sega 32X", "Sega - Dreamcast": "Sega Dreamcast", "Sega - Game Gear": "Sega Game Gear",
    "Sega - Master System - Mark III": "Sega Master System", "Sega - Mega Drive - Genesis": "Sega Genesis",
    "Sega - Mega-CD - Sega CD": "Sega CD", "Sega - SG-1000": "Sega SG-1000", "Sega - Saturn": "Sega Saturn",
    "Sega - PICO": "Sega Pico",
    "Sony - PlayStation": "Sony Playstation", "Sony - PlayStation 2": "Sony Playstation 2",
    "Sony - PlayStation 3": "Sony Playstation 3", "Sony - PlayStation Portable": "Sony PSP",
    "Sony - PlayStation Vita": "Sony Playstation Vita",
    "The 3DO Company - 3DO": "3DO Interactive Multiplayer", "Philips - CD-i": "Philips CD-i",
    "Coleco - ColecoVision": "ColecoVision", "Mattel - Intellivision": "Mattel Intellivision",
}


def key(title):
    """The match key of a title: lower case, accents folded, "&" as "and", a leading or
    trailing "the" dropped, then letters and digits only."""
    text = "".join(FOLD.get(ch, ch) for ch in title.lower())
    text = text.replace("&", " and ")
    for article in (", the ", ", the-", ", the:"):
        text = text.replace(article, " ")
    if text.endswith(", the"):
        text = text[:-5]
    text = text.strip()
    if text.startswith("the "):
        text = text[4:]
    return "".join(ch for ch in text if ("a" <= ch <= "z") or ("0" <= ch <= "9"))


def bucket(k):
    first = k[0]
    return "0" if first.isdigit() else first


def slug(platform):
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in platform)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def download(target):
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "launchbox-covers builder"})
    with urllib.request.urlopen(request, timeout=120) as answer, open(target, "wb") as out:
        shutil.copyfileobj(answer, out)
        modified = answer.headers.get("Last-Modified")
    return email.utils.parsedate_to_datetime(modified).isoformat() if modified else ""


def read(zip_path):
    games = {}  # DatabaseID -> (name, platform)
    alternates = defaultdict(list)
    covers = defaultdict(dict)  # DatabaseID -> {type: {region: file}}
    with zipfile.ZipFile(zip_path) as archive, archive.open("Metadata.xml") as xml:
        for _, element in ET.iterparse(xml):
            tag = element.tag
            if tag == "Game":
                game_id = element.findtext("DatabaseID")
                name = element.findtext("Name")
                platform = element.findtext("Platform")
                if game_id and name and platform:
                    games[game_id] = (name.strip(), platform.strip())
                element.clear()
            elif tag == "GameAlternateName":
                game_id = element.findtext("DatabaseID")
                name = element.findtext("AlternateName")
                if game_id and name:
                    alternates[game_id].append(name.strip())
                element.clear()
            elif tag == "GameImage":
                kind = element.findtext("Type")
                if kind in IMAGE_TYPES:
                    game_id = element.findtext("DatabaseID")
                    region = (element.findtext("Region") or "").strip()
                    file = (element.findtext("FileName") or "").strip()
                    if game_id and file and "/" not in file:
                        covers[game_id].setdefault(kind, {}).setdefault(region, file)
                element.clear()
    return games, alternates, covers


def build(zip_path, source_modified):
    games, alternates, covers = read(zip_path)
    tables = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # platform -> bucket -> key -> games
    face_tables = defaultdict(lambda: defaultdict(dict))  # platform -> bucket -> id -> faces
    counts = defaultdict(int)
    face_counts = defaultdict(int)
    for game_id, (name, platform) in games.items():
        kinds = covers.get(game_id)
        if not kinds or not any(kind in kinds for kind in COVER_TYPES):
            continue
        regions = next(kinds[kind] for kind in COVER_TYPES if kind in kinds)
        entry = [int(game_id), name, sorted([region, file] for region, file in regions.items())]
        faces = {}
        for face, types in FACE_TYPES.items():
            found = next((kinds[kind] for kind in types if kind in kinds), None)
            if found:
                faces[face] = sorted([region, file] for region, file in found.items())
                face_counts[face] += 1
        counts[platform] += 1
        seen = set()
        for title in [name] + alternates.get(game_id, []):
            k = key(title)
            if k and k not in seen:
                seen.add(k)
                tables[platform][bucket(k)][k].append(entry)
                if faces:
                    face_tables[platform][bucket(k)][game_id] = faces

    data = ROOT / "data"
    staging = Path(tempfile.mkdtemp(dir=ROOT, prefix=".data-"))
    platforms = {}
    for platform in sorted(tables):
        folder = slug(platform)
        buckets = tables[platform]
        for name in sorted(buckets):
            target = staging / "covers" / folder / f"{name}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            body = {k: sorted(v) for k, v in sorted(buckets[name].items())}
            target.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        platforms[platform] = {"dir": folder, "games": counts[platform], "buckets": sorted(buckets)}
        face_buckets = face_tables.get(platform, {})
        for name in sorted(face_buckets):
            target = staging / "faces" / folder / f"{name}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            body = {game_id: face_buckets[name][game_id] for game_id in sorted(face_buckets[name], key=int)}
            target.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if face_buckets:
            platforms[platform]["faces"] = sorted(face_buckets)
    missing = sorted(lb for lb in LIBRETRO.values() if lb not in platforms)
    if missing:
        print("warning: libretro names point at platforms without covers:", ", ".join(missing), file=sys.stderr)
    manifest = {
        "format": FORMAT,
        "version": datetime.date.today().isoformat(),
        "source": SOURCE,
        "source_modified": source_modified,
        "images": IMAGES,
        "face_kinds": list(FACE_TYPES),
        "libretro": dict(sorted(LIBRETRO.items())),
        "platforms": platforms,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if data.exists():
        shutil.rmtree(data)
    staging.rename(data)
    total = sum(counts.values())
    print(f"data/: {len(platforms)} platforms, {total} games with a front cover")
    print("faces: " + ", ".join(f"{face} {face_counts[face]}" for face in FACE_TYPES))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", help="a Metadata.zip already downloaded")
    args = parser.parse_args()
    if args.zip:
        build(Path(args.zip), "")
        return
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "Metadata.zip"
        modified = download(target)
        build(target, modified)


if __name__ == "__main__":
    main()
