#!/usr/bin/env python3
"""One-time migration: seed the adhand database from the legacy .settings file
(lat,lng,method,fajr_volume_millibels,volume_millibels).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from config import LEGACY_SETTINGS_PATH


def millibels_to_percent(mb: int) -> int:
    """Legacy volumes were millibels for `cvlc --gain` (0 = default). Map to 0-100."""
    if mb <= -30000:
        return 0
    return max(0, min(100, round(50 + mb / 60)))


def main() -> None:
    if not LEGACY_SETTINGS_PATH.exists():
        print("No legacy .settings file found; nothing to migrate.")
        return
    raw = LEGACY_SETTINGS_PATH.read_text().strip().split(",")
    lat, lng, method = raw[0], raw[1], raw[2]
    fajr_vol = int(raw[3]) if len(raw) > 3 and raw[3] else 0
    other_vol = int(raw[4]) if len(raw) > 4 and raw[4] else 0

    db.init()
    if lat:
        db.set_setting("lat", float(lat))
    if lng:
        db.set_setting("lng", float(lng))
    if method:
        db.set_setting("method", method)
    db.update_prayer("fajr", {"volume": millibels_to_percent(fajr_vol)})
    for name in ("dhuhr", "asr", "maghrib", "isha"):
        db.update_prayer(name, {"volume": millibels_to_percent(other_vol)})
    print(f"Migrated: lat={lat} lng={lng} method={method} "
          f"fajr_vol={millibels_to_percent(fajr_vol)}% other_vol={millibels_to_percent(other_vol)}%")


if __name__ == "__main__":
    main()
