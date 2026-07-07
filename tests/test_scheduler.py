"""Tests for the pure/synchronous logic in scheduler.py.

We cover: is_muted(), consume_skip(), compute_times(), and schedule_today()
(including offset-hook scheduling). Audio playback paths (async play_* which
require a real player) are intentionally NOT unit tested here — see the report.
"""
import asyncio
from datetime import date, datetime

import pytest
from freezegun import freeze_time

import db
import scheduler


# ---------- is_muted ----------

def test_is_muted_false_when_unset(temp_db):
    assert scheduler.is_muted() is False


@freeze_time("2026-07-07 06:00:00")
def test_is_muted_true_when_future(temp_db):
    db.set_setting("mute_until", "2026-07-07T07:00:00")
    assert scheduler.is_muted() is True


@freeze_time("2026-07-07 06:00:00")
def test_is_muted_false_when_past(temp_db):
    db.set_setting("mute_until", "2026-07-07T05:00:00")
    assert scheduler.is_muted() is False


# ---------- consume_skip ----------

@freeze_time("2026-07-07 06:00:00")
def test_consume_skip_matches_once(temp_db):
    db.set_setting("skip_next", {"name": "fajr", "date": date.today().isoformat()})
    assert scheduler.consume_skip("fajr") is True
    # one-time: the flag is cleared after being consumed
    assert scheduler.consume_skip("fajr") is False
    assert db.get_setting("skip_next") is None


@freeze_time("2026-07-07 06:00:00")
def test_consume_skip_wrong_name(temp_db):
    db.set_setting("skip_next", {"name": "fajr", "date": date.today().isoformat()})
    assert scheduler.consume_skip("dhuhr") is False


@freeze_time("2026-07-07 06:00:00")
def test_consume_skip_stale_date(temp_db):
    db.set_setting("skip_next", {"name": "fajr", "date": "2020-01-01"})
    assert scheduler.consume_skip("fajr") is False


def test_consume_skip_unset(temp_db):
    assert scheduler.consume_skip("fajr") is False


# ---------- compute_times ----------

def test_compute_times_none_without_location(temp_db):
    assert scheduler.compute_times() is None


def _set_seattle(method="ISNA"):
    db.set_setting("lat", 47.6)
    db.set_setting("lng", -122.3)
    db.set_setting("method", method)


def test_compute_times_shape_and_format(temp_db):
    _set_seattle()
    data = scheduler.compute_times(date(2026, 7, 7))
    assert data is not None
    assert set(data["times"]) == {"fajr", "dhuhr", "asr", "maghrib", "isha"}
    assert set(data["extras"]) >= {"imsak", "sunrise", "midnight"}
    for hhmm in data["times"].values():
        hh, mm = hhmm.split(":")
        assert len(hh) == 2 and len(mm) == 2
        assert 0 <= int(hh) <= 23
        assert 0 <= int(mm) <= 59


# ---------- schedule_today (APScheduler) ----------
#
# AsyncIOScheduler.start() requires a running event loop, so each scheduling
# scenario runs its body inside asyncio.run(). schedule_today() itself is
# synchronous; we call it from within the loop after starting the scheduler,
# then read the jobs back, then shut down — all under one frozen clock.
#
# compute_times() derives prayer times from the machine's local timezone
# (time.timezone), so raw times differ between a dev Mac and a UTC CI runner and
# can even wrap past midnight. To keep the *scheduling* assertions deterministic
# and timezone-independent, these tests stub compute_times() with fixed HH:MM
# values well after the frozen 03:00 clock. The real compute_times() output is
# covered separately by the format/shape tests above.

FIXED_TIMES = {
    "times": {"fajr": "05:00", "dhuhr": "13:00", "asr": "17:00",
              "maghrib": "21:00", "isha": "22:30"},
    "extras": {"imsak": "04:50", "sunrise": "05:30", "midnight": "01:00"},
}


@pytest.fixture
def fixed_times(monkeypatch):
    """Force schedule_today() to use deterministic, tz-independent prayer times."""
    monkeypatch.setattr(scheduler, "compute_times", lambda day=None: FIXED_TIMES)


def _run_scheduling(body):
    """Start the scheduler in a fresh event loop, run ``body()``, shut down.

    ``body`` is a plain callable returning whatever the test wants to assert on.
    """
    async def runner():
        for job in scheduler.scheduler.get_jobs():
            job.remove()
        if not scheduler.scheduler.running:
            scheduler.scheduler.start()
        try:
            return body()
        finally:
            for job in scheduler.scheduler.get_jobs():
                job.remove()
            scheduler.shutdown()

    return asyncio.run(runner())


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_creates_prayer_jobs(temp_db, fixed_times):
    _set_seattle()

    def body():
        data = scheduler.schedule_today()
        assert data is not None
        return {j["id"] for j in scheduler.scheduled_jobs()}

    ids = _run_scheduling(body)
    # Frozen at 03:00 local, all five prayers are still in the future today.
    assert {"prayer-fajr", "prayer-dhuhr", "prayer-asr",
            "prayer-maghrib", "prayer-isha"} <= ids


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_none_without_location(temp_db):
    def body():
        assert scheduler.schedule_today() is None
        return scheduler.scheduled_jobs()

    assert _run_scheduling(body) == []


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_offset_hook(temp_db, fixed_times):
    _set_seattle()
    # July 7 2026 is a Tuesday (weekday 1). Schedule a -45 min hook on dhuhr.
    hid = db.add_hook("Kahf", "after", ["dhuhr"], [1], "10-friday-kahf.sh",
                      offset_minutes=-45)

    def body():
        scheduler.schedule_today()
        return {j["id"]: j["at"] for j in scheduler.scheduled_jobs()}

    jobs = _run_scheduling(body)
    hook_id = f"hook-{hid}-dhuhr"
    assert hook_id in jobs

    # The hook must fire exactly 45 minutes before the dhuhr job.
    dhuhr_at = datetime.fromisoformat(jobs["prayer-dhuhr"])
    hook_at = datetime.fromisoformat(jobs[hook_id])
    assert (dhuhr_at - hook_at).total_seconds() == 45 * 60


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_offset_hook_wrong_weekday_skipped(temp_db, fixed_times):
    _set_seattle()
    # Restrict to Friday only (4); frozen day is Tuesday -> no hook job.
    hid = db.add_hook("Kahf", "after", ["dhuhr"], [4], "10-friday-kahf.sh",
                      offset_minutes=-45)

    def body():
        scheduler.schedule_today()
        return {j["id"] for j in scheduler.scheduled_jobs()}

    ids = _run_scheduling(body)
    assert f"hook-{hid}-dhuhr" not in ids


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_skips_disabled_prayer(temp_db, fixed_times):
    _set_seattle()
    db.update_prayer("asr", {"enabled": 0})

    def body():
        scheduler.schedule_today()
        return {j["id"] for j in scheduler.scheduled_jobs()}

    ids = _run_scheduling(body)
    assert "prayer-asr" not in ids
    assert "prayer-fajr" in ids


@freeze_time("2026-07-07 03:00:00")
def test_schedule_today_reminder_job(temp_db, fixed_times):
    _set_seattle()
    db.update_prayer("isha", {"reminder_minutes": 10})

    def body():
        scheduler.schedule_today()
        return {j["id"] for j in scheduler.scheduled_jobs()}

    assert "reminder-isha" in _run_scheduling(body)
