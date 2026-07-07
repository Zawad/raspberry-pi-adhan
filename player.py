"""Audio playback. Prefers cvlc (as on the Pi today), falls back to mpv or afplay for dev machines.

Fade-in requires mpv (ffmpeg afade filter); with cvlc-only the fade is skipped gracefully.
"""
import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import AUDIO_EXTS, MEDIA_DIR
from events import emit, ws_manager


def list_media() -> list[str]:
    return sorted(p.name for p in MEDIA_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def resolve_media(name: str) -> Path:
    path = (MEDIA_DIR / name).resolve()
    if path.parent != MEDIA_DIR.resolve() or path.suffix.lower() not in AUDIO_EXTS or not path.is_file():
        raise FileNotFoundError(f"Unknown audio file: {name}")
    return path


def _build_cmd(path: Path, volume: int, device: str | None,
               fade: int = 0, duration: int | None = None) -> list[str]:
    """volume is 0-100; 50 is unity gain for vlc."""
    has_mpv = shutil.which("mpv")
    if has_mpv and (fade > 0 or not shutil.which("cvlc")):
        cmd = ["mpv", "--no-video", "--really-quiet", f"--volume={volume}"]
        if fade > 0:
            cmd.append(f"--af=lavfi=[afade=t=in:d={fade}]")
        if duration:
            cmd.append(f"--length={duration}")
        if device:
            cmd.append(f"--audio-device=alsa/{device}")
        return cmd + [str(path)]
    if shutil.which("cvlc"):
        cmd = ["cvlc", "--no-dbus", "--play-and-exit", "--gain", f"{volume / 50:.2f}"]
        if duration:
            cmd += ["--stop-time", str(duration)]
        if device:
            cmd += ["-A", "alsa", "--alsa-audio-device", device]
        return cmd + [str(path)]
    if shutil.which("afplay"):  # macOS dev fallback; no device routing
        cmd = ["afplay", "-v", f"{volume / 100:.2f}"]
        if duration:
            cmd += ["-t", str(duration)]
        return cmd + [str(path)]
    raise RuntimeError("No supported audio player found (need cvlc, mpv, or afplay)")


class Player:
    def __init__(self):
        self._proc: asyncio.subprocess.Process | None = None
        self.current: dict | None = None

    @property
    def playing(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def play(self, mp3: str, volume: int, device: str | None = None, label: str = "test",
                   fade: int = 0, duration: int | None = None) -> None:
        path = resolve_media(mp3)
        await self.stop()
        cmd = _build_cmd(path, volume, device, fade=fade, duration=duration)
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        self.current = {
            "label": label,
            "mp3": mp3,
            "volume": volume,
            "device": device,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await ws_manager.broadcast({"kind": "playing", "playing": self.current})
        asyncio.create_task(self._reap(self._proc))

    async def _reap(self, proc: asyncio.subprocess.Process) -> None:
        await proc.wait()
        if self._proc is proc:
            self.current = None
            self._proc = None
            await ws_manager.broadcast({"kind": "playing", "playing": None})

    async def wait_until_done(self) -> None:
        proc = self._proc
        if proc is not None:
            await proc.wait()

    async def stop(self) -> None:
        if self.playing:
            label = self.current["label"] if self.current else "?"
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
            await emit("stopped", f"Playback stopped ({label})")
        self.current = None
        self._proc = None


player = Player()
