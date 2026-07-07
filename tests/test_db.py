"""Round-trip tests for the SQLite storage layer in db.py."""
import db
from config import PRAYER_NAMES


def test_init_seeds_five_prayers(temp_db):
    prayers = db.get_prayers()
    assert len(prayers) == 5
    assert {p["name"] for p in prayers} == set(PRAYER_NAMES)


def test_init_seeds_fajr_with_fajr_mp3(temp_db):
    from config import DEFAULT_FAJR_MP3, DEFAULT_MP3

    fajr = db.get_prayer("fajr")
    dhuhr = db.get_prayer("dhuhr")
    assert fajr["mp3"] == DEFAULT_FAJR_MP3
    assert dhuhr["mp3"] == DEFAULT_MP3


def test_init_is_idempotent(temp_db):
    db.init()  # a second init must not duplicate seeded prayers
    assert len(db.get_prayers()) == 5


def test_migrations_add_columns(temp_db):
    fajr = db.get_prayer("fajr")
    # columns added by MIGRATIONS should be present with their defaults
    assert fajr["offset_minutes"] == 0
    assert fajr["reminder_minutes"] == 0
    assert "dua_mp3" in fajr


def test_setting_round_trip_json(temp_db):
    db.set_setting("lat", 47.6)
    db.set_setting("skip_next", {"name": "fajr", "date": "2026-07-07"})
    assert db.get_setting("lat") == 47.6
    assert db.get_setting("skip_next") == {"name": "fajr", "date": "2026-07-07"}


def test_get_setting_default(temp_db):
    assert db.get_setting("does-not-exist") is None
    assert db.get_setting("does-not-exist", "fallback") == "fallback"


def test_set_setting_upsert(temp_db):
    db.set_setting("method", "ISNA")
    db.set_setting("method", "MWL")  # overwrite
    assert db.get_setting("method") == "MWL"


def test_update_prayer(temp_db):
    db.update_prayer("dhuhr", {"volume": 55, "enabled": 0, "offset_minutes": -3})
    dhuhr = db.get_prayer("dhuhr")
    assert dhuhr["volume"] == 55
    assert dhuhr["enabled"] == 0
    assert dhuhr["offset_minutes"] == -3


def test_update_prayer_ignores_unknown_fields(temp_db):
    db.update_prayer("asr", {"volume": 42, "bogus": "x"})
    assert db.get_prayer("asr")["volume"] == 42


def test_add_and_get_hook(temp_db):
    hid = db.add_hook("Kahf", "after", ["dhuhr"], [4], "10-friday-kahf.sh",
                      offset_minutes=-45, volume=70)
    hook = db.get_hook(hid)
    assert hook is not None
    assert hook["name"] == "Kahf"
    assert hook["position"] == "after"
    assert hook["prayers"] == ["dhuhr"]      # JSON decoded back to a list
    assert hook["days"] == [4]
    assert hook["offset_minutes"] == -45
    assert hook["volume"] == 70
    assert hook["enabled"] == 1


def test_get_hooks_ordered(temp_db):
    a = db.add_hook("A", "before", ["fajr"], [0], "10-friday-kahf.sh")
    b = db.add_hook("B", "after", ["isha"], [1], "10-friday-kahf.sh")
    ids = [h["id"] for h in db.get_hooks()]
    assert ids == [a, b]


def test_update_hook(temp_db):
    hid = db.add_hook("H", "before", ["fajr"], [0], "10-friday-kahf.sh")
    db.update_hook(hid, {"name": "Renamed", "days": [1, 2], "enabled": False})
    hook = db.get_hook(hid)
    assert hook["name"] == "Renamed"
    assert hook["days"] == [1, 2]
    assert hook["enabled"] == 0


def test_delete_hook(temp_db):
    hid = db.add_hook("H", "before", ["fajr"], [0], "10-friday-kahf.sh")
    db.delete_hook(hid)
    assert db.get_hook(hid) is None
    assert db.get_hooks() == []


def test_event_log_round_trip(temp_db):
    db.log_event("adhan", "played fajr")
    db.log_event("error", "boom")
    events = db.get_events()
    assert len(events) == 2
    # newest first
    assert events[0]["type"] == "error"
    assert events[0]["detail"] == "boom"
    assert events[1]["type"] == "adhan"
