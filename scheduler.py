"""In-process prayer scheduler. Replaces the cron-rewriting approach:
computes today's times with the vendored praytimes engine and schedules
playback jobs directly. Recomputes just after midnight and whenever
settings change (via reschedule()).
"""
import time as time_mod
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

import db
from config import PRAYER_NAMES
from events import emit
from hooks import run_hooks
from player import player
from praytimes import PrayTimes

scheduler = AsyncIOScheduler()


def compute_times(day: date | None = None) -> dict[str, str] | None:
    """Prayer times as HH:MM strings for the given day, or None if location unset."""
    lat, lng = db.get_setting("lat"), db.get_setting("lng")
    method = db.get_setting("method", "ISNA")
    if lat is None or lng is None:
        return None
    day = day or date.today()
    pt = PrayTimes()
    pt.setMethod(method)
    utc_offset = -(time_mod.timezone / 3600)
    is_dst = time_mod.localtime().tm_isdst
    times = pt.getTimes((day.year, day.month, day.day), (lat, lng), utc_offset, is_dst)
    return {name: times[name] for name in PRAYER_NAMES}


async def play_prayer(name: str) -> None:
    prayer = db.get_prayer(name)
    if not prayer or not prayer["enabled"]:
        return
    await emit("adhan", f"Playing {name} adhan ({prayer['mp3']}, volume {prayer['volume']})")
    await run_hooks("before", name)
    await player.play(prayer["mp3"], prayer["volume"], prayer["device"], label=name)
    await player.wait_until_done()
    await run_hooks("after", name)
    await emit("adhan", f"Finished {name} adhan")


def schedule_today() -> dict[str, str] | None:
    """(Re)create today's playback jobs for prayers still in the future."""
    for job in scheduler.get_jobs():
        if job.id.startswith("prayer-"):
            job.remove()
    times = compute_times()
    if times is None:
        return None
    now = datetime.now()
    for name, hhmm in times.items():
        prayer = db.get_prayer(name)
        if not prayer or not prayer["enabled"]:
            continue
        hour, minute = map(int, hhmm.split(":"))
        run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_at > now:
            scheduler.add_job(
                play_prayer, DateTrigger(run_date=run_at),
                args=[name], id=f"prayer-{name}", replace_existing=True,
            )
    return times


async def reschedule(reason: str = "settings changed") -> None:
    times = schedule_today()
    if times:
        await emit("schedule", f"Rescheduled ({reason}): " + ", ".join(f"{k} {v}" for k, v in times.items()))
    else:
        await emit("schedule", f"Location not set — nothing scheduled ({reason})")


def start() -> None:
    scheduler.add_job(
        reschedule, CronTrigger(hour=0, minute=5),
        kwargs={"reason": "daily recompute"}, id="daily-recompute",
    )
    scheduler.start()
    schedule_today()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def next_prayer() -> dict | None:
    """The soonest scheduled prayer job, for the status endpoint."""
    upcoming = [
        {"name": j.id.removeprefix("prayer-"), "at": j.next_run_time.isoformat()}
        for j in scheduler.get_jobs()
        if j.id.startswith("prayer-") and j.next_run_time
    ]
    return min(upcoming, key=lambda p: p["at"]) if upcoming else None
