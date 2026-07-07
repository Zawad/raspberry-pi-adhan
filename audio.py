"""Enumerate audio output devices."""
import asyncio
import shutil


async def list_devices() -> list[dict]:
    """Return selectable output devices. Always includes the system default."""
    devices = [{"id": None, "label": "System default"}]
    if not shutil.which("aplay"):
        return devices
    try:
        proc = await asyncio.create_subprocess_exec(
            "aplay", "-L", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await proc.communicate()
    except OSError:
        return devices
    lines = out.decode(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line and not line[0].isspace():
            dev_id = line.strip()
            desc = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1][:1].isspace() else dev_id
            # keep the useful ones; raw ALSA output is very noisy
            if dev_id.split(":")[0] in ("default", "sysdefault", "plughw", "bluealsa"):
                devices.append({"id": dev_id, "label": f"{dev_id} — {desc}"})
        i += 1
    return devices
