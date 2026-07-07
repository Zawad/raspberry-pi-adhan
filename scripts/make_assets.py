#!/usr/bin/env python3
"""Generate the PWA icons (crescent on dark) and the reminder chime.
Pure stdlib so it runs anywhere; outputs are committed, rerun only to tweak.
"""
import math
import struct
import sys
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BG = (15, 20, 25)        # matches the web UI background
GOLD = (200, 169, 106)   # matches the web UI accent


def crescent_alpha(u: float, v: float) -> float:
    """Coverage 0..1 of the crescent-and-star artwork at unit coords (u, v)."""
    def inside(cx, cy, r):
        return math.hypot(u - cx, v - cy) <= r

    # crescent = big circle minus offset bite
    if inside(0.47, 0.52, 0.30) and not inside(0.585, 0.475, 0.255):
        return 1.0
    if inside(0.66, 0.30, 0.045):  # star dot
        return 1.0
    return 0.0


def make_icon(size: int, out: Path) -> None:
    rows = []
    ss = 2  # 2x2 supersampling for soft edges
    for y in range(size):
        row = bytearray([0])  # PNG filter type 0
        for x in range(size):
            cov = sum(
                crescent_alpha((x + (i + .5) / ss) / size, (y + (j + .5) / ss) / size)
                for i in range(ss) for j in range(ss)
            ) / (ss * ss)
            px = tuple(round(b + (g - b) * cov) for b, g in zip(BG, GOLD))
            row += bytes(px)
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    out.write_bytes(png)
    print(f"wrote {out} ({size}x{size})")


def make_chime(out: Path) -> None:
    rate = 22050
    seconds = 3.0
    n = int(rate * seconds)
    samples = []
    # two soft bell strikes: E5 then A5, each with a couple of partials
    strikes = [(0.0, 659.25), (0.9, 880.0)]
    for i in range(n):
        t = i / rate
        s = 0.0
        for start, freq in strikes:
            dt = t - start
            if dt < 0:
                continue
            env = min(dt / 0.005, 1.0) * math.exp(-dt * 2.2)
            s += env * (
                0.6 * math.sin(2 * math.pi * freq * dt)
                + 0.25 * math.sin(2 * math.pi * freq * 2.0 * dt)
                + 0.1 * math.sin(2 * math.pi * freq * 2.99 * dt)
            )
        samples.append(int(max(-1.0, min(1.0, s * 0.5)) * 32767))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{n}h", *samples))
    print(f"wrote {out} ({seconds}s)")


if __name__ == "__main__":
    # The PWA icons in web/ are resized from the brand icon in the separate
    # mobile-app repo (Workspace/adhan .../assets/images/icon.png) — do not
    # overwrite them unless explicitly asked (--icons regenerates the old
    # generated crescent artwork instead).
    if "--icons" in sys.argv:
        web = ROOT / "web"
        make_icon(192, web / "icon-192.png")
        make_icon(512, web / "icon-512.png")
        make_icon(180, web / "apple-touch-icon.png")
    make_chime(ROOT / "chime.wav")
