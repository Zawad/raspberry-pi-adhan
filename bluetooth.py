"""Bluetooth speaker management via bluetoothctl. Absent (e.g. on dev Macs) -> available=False."""
import asyncio
import re
import shutil

_DEVICE_RE = re.compile(r"^Device ([0-9A-F:]{17}) (.+)$", re.MULTILINE | re.IGNORECASE)
_MAC_RE = re.compile(r"^[0-9A-F:]{17}$", re.IGNORECASE)


def available() -> bool:
    return shutil.which("bluetoothctl") is not None


async def _run(*args: str, timeout: int = 20) -> str:
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"bluetoothctl {' '.join(args)} timed out")
    return out.decode(errors="replace")


def _parse_devices(output: str) -> list[dict]:
    return [{"mac": m.group(1), "name": m.group(2).strip()} for m in _DEVICE_RE.finditer(output)]


async def _connected_macs() -> set[str]:
    try:
        out = await _run("devices", "Connected", timeout=10)
        return {d["mac"] for d in _parse_devices(out)}
    except RuntimeError:
        return set()


async def status() -> dict:
    if not available():
        return {"available": False, "devices": []}
    # "devices Paired" on bluez >= 5.65, "paired-devices" before
    out = await _run("devices", "Paired", timeout=10)
    devices = _parse_devices(out)
    if not devices:
        devices = _parse_devices(await _run("paired-devices", timeout=10))
    connected = await _connected_macs()
    for d in devices:
        d["connected"] = d["mac"] in connected
    return {"available": True, "devices": devices}


async def scan(seconds: int = 8) -> list[dict]:
    """Scan for nearby devices; returns unpaired discoveries."""
    await _run("--timeout", str(seconds), "scan", "on", timeout=seconds + 10)
    found = _parse_devices(await _run("devices", timeout=10))
    paired = {d["mac"] for d in (await status())["devices"]}
    return [d for d in found if d["mac"] not in paired]


def _check_mac(mac: str) -> str:
    if not _MAC_RE.match(mac):
        raise ValueError(f"Invalid MAC address: {mac}")
    return mac


async def pair(mac: str) -> str:
    mac = _check_mac(mac)
    out = await _run("pair", mac, timeout=30)
    await _run("trust", mac, timeout=10)
    out += await _run("connect", mac, timeout=20)
    return out


async def connect(mac: str) -> str:
    return await _run("connect", _check_mac(mac), timeout=20)


async def disconnect(mac: str) -> str:
    return await _run("disconnect", _check_mac(mac), timeout=20)


async def forget(mac: str) -> str:
    return await _run("remove", _check_mac(mac), timeout=10)
