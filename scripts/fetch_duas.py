#!/usr/bin/env python3
"""Download dua recitations from hisnmuslim.com (official Hisn al-Muslim site).

The audio is fetched from the source at install time rather than committed to
this repo, since the site distributes freely but publishes no formal license.
API reference: https://www.hisnmuslim.com/api/ar/husn_ar.json
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# filename -> hisnmuslim.com audio id (see api/ar/{chapter}.json)
DUAS = {
    "Dua-After-Adhan.mp3": 25,        # اللهم رب هذه الدعوة التامة (chapter 15)
    "Dua-Replying-Muadhin.mp3": 22,   # repeating after the muadhin (chapter 15)
    "Dua-Iftar.mp3": 176,             # ذهب الظمأ وابتلت العروق (chapter 68)
}

URL = "https://www.hisnmuslim.com/audio/ar/{id}.mp3"


def main() -> None:
    failed = 0
    for name, audio_id in DUAS.items():
        dest = ROOT / name
        if dest.exists():
            print(f"already have {name}")
            continue
        url = URL.format(id=audio_id)
        try:
            print(f"fetching {name} <- {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.4 (adhand dua fetcher)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if not data.startswith((b"ID3", b"\xff")):
                raise ValueError("response is not an mp3")
            dest.write_bytes(data)
            print(f"  wrote {len(data) // 1024} KB")
        except Exception as exc:
            failed += 1
            print(f"  FAILED: {exc}")
    if failed:
        print(f"{failed} download(s) failed — rerun later; the daemon works without them.")
        sys.exit(1)


if __name__ == "__main__":
    main()
