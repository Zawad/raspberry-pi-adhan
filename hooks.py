"""Hook rules: run allow-listed scripts around adhan times, filtered by prayer and weekday.

Scripts are the executable files living in before-hooks.d/ and after-hooks.d/.
The web app can only reference scripts by filename from those directories — it
can never submit an arbitrary command.

Timing: a hook with offset_minutes == 0 runs in-sequence with adhan playback
(before-hooks right before, after-hooks right after). A non-zero offset makes
it an independently scheduled job at prayer time + offset (negative = earlier),
e.g. Surah Al-Kahf 45 minutes before dhuhr on Fridays.

Scripts receive context via environment variables:
  PRAYER        the prayer this run is tied to
  HOOK_NAME     the hook rule's display name
  HOOK_VOLUME   the rule's volume (0-100), only when set in the app
  ADHAND_API    the daemon API base url
"""
import asyncio
import os
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
    # plain filenames only (no traversal); symlinks into the sibling hook dir
    # are allowed so one script can appear in both catalogs
    if "/" in name or name.startswith("."):
        raise FileNotFoundError(f"Unknown {position}-hook script: {name}")
    path = _dir_for(position) / name
    if not path.is_file():
        raise FileNotFoundError(f"Unknown {position}-hook script: {name}")
    return path


def _api_base() -> str:
    return db.get_setting("api_base", "http://127.0.0.1:8000/api")


async def run_hook(hook: dict, prayer: str) -> None:
    """Execute one hook rule's script with context env. Raises on failure."""
    script = resolve_script(hook["position"], hook["script"])
    env = os.environ | {
        "PRAYER": prayer,
        "HOOK_NAME": hook["name"],
        "ADHAND_API": _api_base(),
    }
    if hook.get("volume") is not None:
        env["HOOK_VOLUME"] = str(hook["volume"])
    proc = await asyncio.create_subprocess_exec(
        str(script), env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.wait(), timeout=HOOK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"timed out after {HOOK_TIMEOUT_SECONDS}s (long-running hooks should detach)")


async def run_hooks(position: str, prayer: str, when: datetime | None = None) -> None:
    """Run enabled offset-0 hooks matching this position, prayer, and weekday (0=Mon)."""
    weekday = (when or datetime.now()).weekday()
    for hook in db.get_hooks():
        if not hook["enabled"] or hook["position"] != position:
            continue
        if (hook.get("offset_minutes") or 0) != 0:
            continue  # scheduled independently by the scheduler
        if prayer not in hook["prayers"] or weekday not in hook["days"]:
            continue
        try:
            await run_hook(hook, prayer)
            await emit("hook", f"Ran {position}-hook '{hook['name']}' ({hook['script']}) for {prayer}")
        except Exception as exc:
            await emit("error", f"{position}-hook '{hook['name']}' failed: {exc}")


async def run_scheduled_hook(hook_id: int, prayer: str, force: bool = False) -> None:
    """Fire an offset hook at its scheduled time (rechecks state at fire time)."""
    hook = db.get_hook(hook_id)
    if not hook or (not hook["enabled"] and not force):
        return
    from scheduler import is_muted  # late import to avoid a cycle
    if is_muted() and not force:
        await emit("skipped", f"Hook '{hook['name']}' skipped (muted)")
        return
    try:
        await run_hook(hook, prayer)
        offset = hook.get("offset_minutes") or 0
        rel = f"{abs(offset)} min {'before' if offset < 0 else 'after'} {prayer}"
        await emit("hook", f"Ran hook '{hook['name']}' ({rel})")
    except Exception as exc:
        await emit("error", f"Hook '{hook['name']}' failed: {exc}")
