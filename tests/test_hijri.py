"""Tests for hijri.py. Kept minimal and robust: we assert on the STABLE public
behaviour of ramadan_active() (mode on/off overrides the date) and the shape of
today_hijri(). We deliberately do NOT assert on the hijri_offset feature — that
is owned/covered by another agent.
"""
import db
import hijri


def test_today_hijri_shape(temp_db):
    h = hijri.today_hijri()
    # hijridate is installed in this env; if it were missing the function would
    # return None, which is also a valid contract.
    if h is None:
        return
    assert set(h) >= {"day", "month", "year", "text"}
    assert 1 <= h["month"] <= 12
    assert 1 <= h["day"] <= 30
    assert isinstance(h["text"], str) and h["text"]


def test_ramadan_mode_on_is_true_regardless_of_date(temp_db):
    db.set_setting("ramadan_mode", "on")
    assert hijri.ramadan_active() is True


def test_ramadan_mode_off_is_false_regardless_of_date(temp_db):
    db.set_setting("ramadan_mode", "off")
    assert hijri.ramadan_active() is False


def test_ramadan_mode_auto_returns_bool(temp_db):
    db.set_setting("ramadan_mode", "auto")
    # In 'auto' mode the answer depends on the real Hijri date; only assert type.
    assert isinstance(hijri.ramadan_active(), bool)


def test_ramadan_default_mode_is_auto(temp_db):
    # No setting stored -> default 'auto' -> a plain bool, never an error.
    assert isinstance(hijri.ramadan_active(), bool)
