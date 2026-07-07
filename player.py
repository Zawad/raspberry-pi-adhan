"""Audio playback. Prefers mpv (live volume/pause via its JSON IPC socket, fade
filter); falls back to cvlc (as on the original Pi setup) or afplay (dev Macs).
With non-mpv players, pause/resume works via SIGSTOP/SIGCONT but live volume
changes are unsupported.
"""
import asyncio
import json
import shutil
import signal
from datetime import datetime, timezone
from pathlib import Path

from config import AUDIO_EXTS, MEDIA_DIR
from events import emit, ws_manager

IPC_SOCKET = Path("/tmp/adhand-mpv.sock")


def list_media() -> list[str]:
    return sorted(p.name for p in MEDIA_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def resolve_media(name: str) -> Path:
    path = (MEDIA_DIR / name).resolve()
    if path.parent != MEDIA_DIR.resolve() or path.suffix.lower() not in AUDIO_EXTS or not path.is_file():
        raise FileNotFoundError(f"Unknown audio file: {name}")
    return path


def _build_cmd(path: Path, volume: int, device: str | None,
               fade: int = 0, duration: int | None = None) -> tuple[list[str], bool]:
    """Returns (command, has_ipc). volume is 0-100; 50 is unity gain for vlc."""
    if shutil.which("mpv"):
        cmd = ["mpv", "--no-video", "--really-quiet", f"--volume={volume}",
               f"--input-ipc-server={IPC_SOCKET}"]
        if fade > 0:
            cmd.append(f"--af=lavfi=[afade=t=in:d={fade}]")
        if duration:
            cmd.append(f"--length={duration}")
        if device:
            cmd.append(f"--audio-device=alsa/{device}")
        return cmd + [str(path)], True
    if shutil.which("cvlc"):
        cmd = ["cvlc", "--no-dbus", "--play-and-exit", "--gain", f"{volume / 50:.2f}"]
        if duration:
            cmd += ["--stop-time", str(duration)]
        if device:
            cmd += ["-A", "alsa", "--alsa-audio-device", device]
        return cmd + [str(path)], False
    if shutil.which("afplay"):  # macOS dev fallback; no device routing
        cmd = ["afplay", "-v", f"{volume / 100:.2f}"]
        if duration:
            cmd += ["-t", str(duration)]
        return cmd + [str(path)], False
    raise RuntimeError("No supported audio player found (need mpv, cvlc, or afplay)")


class Player:
    def __init__(self):
        self._proc: asyncio.subprocess.Process | None = None
        self._has_ipc = False
        self.current: dict | None = None

    @property
    def playing(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def _broadcast(self) -> None:
        await ws_manager.broadcast({"kind": "playing", "playing": self.current})

    async def _ipc(self, command: list) -> None:
        reader, writer = await asyncio.open_unix_connection(str(IPC_SOCKET))
        writer.write(json.dumps({"command": command}).encode() + b"\n")
        await writer.drain()
        writer.close()

    async def play(self, mp3: str, volume: int, device: str | None = None, label: str = "test",
                   fade: int = 0, duration: int | None = None) -> None:
        path = resolve_media(mp3)
        await self.stop()
        IPC_SOCKET.unlink(missing_ok=True)
        cmd, self._has_ipc = _build_cmd(path, volume, device, fade=fade, duration=duration)
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        self.current = {
            "label": label,
            "mp3": mp3,
            "volume": volume,
            "device": device,
            "paused": False,
            "live_volume": self._has_ipc,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._broadcast()
        asyncio.create_task(self._reap(self._proc))

    async def _reap(self, proc: asyncio.subprocess.Process) -> None:
        await proc.wait()
        if self._proc is proc:
            self.current = None
            self._proc = None
            await self._broadcast()

    async def wait_until_done(self) -> None:
        proc = self._proc
        if proc is not None:
            await proc.wait()

    async def set_pause(self, paused: bool) -> None:
        if not self.playing:
            return
        if self._has_ipc:
            try:
                await self._ipc(["set_property", "pause", paused])
            except OSError:
                self._proc.send_signal(signal.SIGSTOP if paused else signal.SIGCONT)
        else:
            self._proc.send_signal(signal.SIGSTOP if paused else signal.SIGCONT)
        self.current["paused"] = paused
        await self._broadcast()

    async def set_volume(self, volume: int) -> None:
        if not self.playing:
            return
        if not self._has_ipc:
            raise RuntimeError("Live volume needs mpv; current player doesn't support it")
        await self._ipc(["set_property", "volume", volume])
        self.current["volume"] = volume
        await self._broadcast()

    async def stop(self) -> None:
        if self.playing:
            label = self.current["label"] if self.current else "?"
            if self.current and self.current.get("paused"):
                self._proc.send_signal(signal.SIGCONT)  # can't terminate a stopped process cleanly
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
            await emit("stopped", f"Playback stopped ({label})")
        self.current = None
        self._proc = None


player = Player()
