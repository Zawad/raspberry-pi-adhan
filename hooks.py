"""Hook rules: run allow-listed scripts before/after adhan, filtered by prayer and weekday.

Scripts are the executable files already living in before-hooks.d/ and after-hooks.d/.
The web app can only reference scripts by filename from those directories — it can
never submit an arbitrary command.
"""
import asyncio
from datetime import datetime
from pathlib import Path

import db
from config import AFTER_HOOKS_DIR, BEFORE_HOOKS_DIR, HOOK_TIMEOUT_SECONDS
from events import emit


def _dir_for(position: str) -> Path:
    return BEFORE_HOOKS_DIR if position == "before" else AFTER_HOOKS_DIR


def list_scripts() -> dict[str, list[str]]:
    """Available hook scripts, the allow-list the UI picks from."""
    result = {}
    for position in ("before", "after"):
        d = _dir_for(position)
        result[position] = sorted(
            p.name for p in d.iterdir() if p.is_file() and not p.name.startswith(".")
        ) if d.is_dir() else []
    return result


def resolve_script(position: str, name: str) -> Path:
    path = (_dir_for(position) / name).resolve()
    if path.parent != _dir_for(position).resolve() or not path.is_file():
        raise FileNotFoundError(f"Unknown {position}-hook script: {name}")
    return path


async def run_hooks(position: str, prayer: str, when: datetime | None = None) -> None:
    """Run all enabled hooks matching this position, prayer, and day of week (0=Mon)."""
    weekday = (when or datetime.now()).weekday()
    for hook in db.get_hooks():
        if not hook["enabled"] or hook["position"] != position:
            continue
        if prayer not in hook["prayers"] or weekday not in hook["days"]:
            continue
        try:
            script = resolve_script(position, hook["script"])
            proc = await asyncio.create_subprocess_exec(
                str(script),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(proc.wait(), timeout=HOOK_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError(f"timed out after {HOOK_TIMEOUT_SECONDS}s (long-running hooks should detach)")
            await emit("hook", f"Ran {position}-hook '{hook['name']}' ({hook['script']}) for {prayer}")
        except Exception as exc:
            await emit("error", f"{position}-hook '{hook['name']}' failed: {exc}")
