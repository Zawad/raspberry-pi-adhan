"""Central paths and constants for adhand."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MEDIA_DIR = ROOT_DIR  # adhan mp3s live at the repo root
WEB_DIR = ROOT_DIR / "web"
BEFORE_HOOKS_DIR = ROOT_DIR / "before-hooks.d"
AFTER_HOOKS_DIR = ROOT_DIR / "after-hooks.d"
DB_PATH = ROOT_DIR / "adhand.db"
LEGACY_SETTINGS_PATH = ROOT_DIR / ".settings"

PRAYER_NAMES = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

CALC_METHODS = ["MWL", "ISNA", "Egypt", "Makkah", "Karachi", "Tehran", "Jafari"]

DEFAULT_MP3 = "Adhan-Mishary-Rashid-Al-Afasy.mp3"
DEFAULT_FAJR_MP3 = "Adhan-Mishary-Rashid-Al-Afasy-Fajr.mp3"
CHIME_FILE = "chime.wav"

AUDIO_EXTS = {".mp3", ".m4a", ".wav"}
MAX_UPLOAD_MB = 25

ASR_METHODS = ["Standard", "Hanafi"]
HIGH_LAT_RULES = ["NightMiddle", "AngleBased", "OneSeventh", "None"]

# Defaults reflect the ICNA convention used in North America:
# ISNA angles (15/15) with the Hanafi asr school. All remain user-configurable.
DEFAULT_METHOD = "ISNA"
DEFAULT_ASR_METHOD = "Hanafi"
DEFAULT_HIGH_LATS = "NightMiddle"

# user-tunable preferences stored in the settings table: key -> default
PREFERENCE_DEFAULTS = {
    "ramadan_mode": "auto",        # auto | on | off
    "suhoor_enabled": False,
    "suhoor_minutes": 45,          # before fajr
    "suhoor_mp3": CHIME_FILE,
    "jumuah_action": "normal",     # normal | mp3 | skip  (Friday dhuhr)
    "jumuah_mp3": None,
    "fajr_fade_seconds": 0,
    "hijri_offset": 0,             # -2..+2 days, for local moonsighting
}

HOOK_TIMEOUT_SECONDS = 60
