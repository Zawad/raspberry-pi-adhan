"""Pi health readings and self-update. Everything degrades gracefully on dev machines."""
import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path

from config import ROOT_DIR


def _read_cpu_temp() -> float | None:
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return round(int(thermal.read_text().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _uptime_seconds() -> int | None:
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except OSError:
        return None


def _time_synced() -> bool | None:
    if not shutil.which("timedatectl"):
        return None
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out == "yes"
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_version() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT_DIR), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


_started_at = time.time()


def health() -> dict:
    disk = shutil.disk_usage(ROOT_DIR)
    return {
        "cpu_temp_c": _read_cpu_temp(),
        "uptime_seconds": _uptime_seconds(),
        "daemon_uptime_seconds": int(time.time() - _started_at),
        "disk_free_mb": disk.free // (1024 * 1024),
        "load_1m": round(os.getloadavg()[0], 2),
        "time_synced": _time_synced(),
        "version": _git_version(),
    }


async def self_update() -> dict:
    """git pull + pip install, then exit so systemd restarts us on the new code."""
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(ROOT_DIR), "pull", "--ff-only",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    output = out.decode(errors="replace").strip()
    if proc.returncode != 0:
        return {"updated": False, "restarting": False, "output": output}
    if "Already up to date" in output:
        return {"updated": False, "restarting": False, "output": output}

    pip = ROOT_DIR / ".venv" / "bin" / "pip"
    if pip.exists():
        dep = await asyncio.create_subprocess_exec(
            str(pip), "install", "-q", "-r", str(ROOT_DIR / "requirements.txt"),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await dep.wait()

    async def _exit_soon():
        await asyncio.sleep(1)  # let the HTTP response flush
        os._exit(0)  # systemd Restart=always brings us back on the new code

    asyncio.get_event_loop().create_task(_exit_soon())
    return {"updated": True, "restarting": True, "output": output}
