# raspberry-pi-adhan

Raspberry Pi adhan clock, being modernized from a cron-based script into `adhand`:
a LAN-only daemon + web app so family members can control it from their phones.

## Architecture (decided 2026-07)

- **LAN-only by design** — no cloud, no port forwarding. Family phones open
  `http://<pi-hostname>.local:8000` on home Wi-Fi and "Add to Home Screen".
  Remote access was considered (Supabase control plane) and deliberately deferred;
  if ever needed, add Tailscale (zero code changes) or a sync agent later.
- **Daemon modules live flat at the repo root** — single process run by systemd
  (`deploy/adhand.service`, `ExecStart` runs `uvicorn main:app`):
  - `scheduler.py` — APScheduler in-process jobs replace crontab rewriting.
    Recomputes daily at 00:05 and on any settings change. Prayer times computed
    locally by the legacy `praytimes.py` at the repo root.
  - `player.py` — playback via cvlc (Pi), mpv/afplay fallbacks (dev). Volume is
    0–100 (50 = vlc unity gain); legacy used millibels.
  - `hooks.py` — hooks are DB rules (position before/after, prayers, days-of-week
    0=Mon..6=Sun, enabled) that reference scripts by filename from the legacy
    `before-hooks.d/` and `after-hooks.d/` dirs. UI can never submit arbitrary
    shell — scripts on disk are the allow-list.
  - `db.py` — SQLite (`adhand.db`, WAL) with tables: settings (k/v JSON),
    prayers (per-prayer enabled/volume/mp3/device), hooks, events.
  - `routes.py` — REST under `/api` + WebSocket `/api/ws` broadcasting
    playing-state and event-log entries. `main.py` is the FastAPI entry point.
- **`web/`** — static vanilla-JS single page served by FastAPI. No build step.
- **Legacy files** (`updateAzaanTimers.py`, `playAzaan.sh`, `crontab/`, mp3s at
  repo root) are kept until adhand is proven on the Pi;
  `scripts/migrate_settings.py` seeds the DB from the legacy `.settings`.
  `deploy/install.sh` removes the old `rpiAdhanClockJob` cron entries.

## Running

- Dev: `pip install -r requirements.txt && uvicorn main:app --reload`
- Pi: `./deploy/install.sh` then `http://<hostname>.local:8000`

## Conventions / decisions

- No auth yet; trust model is the home Wi-Fi. Next step if wanted: named
  profiles + shared PIN (not per-user passwords).
- mp3s stay at repo root (`config.MEDIA_DIR = ROOT_DIR`) to avoid duplicating
  ~44 MB; player validates requested files resolve inside MEDIA_DIR.
- Days of week are integers 0=Monday..6=Sunday everywhere (Python convention).
- Owner: Zawad (github.com/Zawad/raspberry-pi-adhan). Original upstream README
  describes the legacy cron flow.
