#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Finds each platform's device picture (a photo of the console from the front, on a clear
background) on the LaunchBox Games Database's platform pages, which Metadata.zip leaves out.

    python -I tools/devices.py      # rewrites tools/devices.json and data/manifest.json

tools/devices.json maps a platform's name to the picture's file on images.launchbox-app.com;
build.py copies it into the manifest as each platform's "device".
"""

import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = "https://gamesdb.launchbox-app.com/platforms/images/{}"
LIST = ROOT / "tools" / "devices.json"
MANIFEST = ROOT / "data" / "manifest.json"
MAX_ID = 700
GIVE_UP_AFTER = 150  # missing ids in a row past the last platform


def fetch(platform_id):
    request = urllib.request.Request(PAGE.format(platform_id), headers={"User-Agent": "launchbox-covers"})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            return answer.read().decode("utf-8", "replace")
    except urllib.error.HTTPError:
        return None


def device(page):
    name = re.search(r"<h1[^>]*>([^<]+)", page)
    found = re.search(r'href="https://images\.launchbox-app\.com/(Platforms/[^"]+)"[^>]*data-title="[^"]* - '
                      r'Platform Device Thumb"', page)
    if not name or not found:
        return None, None
    return html.unescape(name.group(1)).strip(), found.group(1)


def main():
    devices = {}
    missing = 0
    for platform_id in range(1, MAX_ID):
        page = fetch(platform_id)
        name, file = device(page) if page else (None, None)
        if page is None or name is None:
            missing += 1
            if missing >= GIVE_UP_AFTER and devices:
                break
        else:
            missing = 0
        if name and file:
            devices[name] = file
        time.sleep(0.3)
    LIST.write_text(json.dumps(dict(sorted(devices.items())), ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, entry in manifest["platforms"].items():
        entry.pop("device", None)
        if name in devices:
            entry["device"] = devices[name]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(devices)} platforms with a device picture")


if __name__ == "__main__":
    main()
