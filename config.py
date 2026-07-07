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
DEFAULT_FAJR_MP3 = "Adhan-fajr.mp3"

HOOK_TIMEOUT_SECONDS = 60
