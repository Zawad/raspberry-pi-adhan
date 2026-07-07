# Raspberry Pi Adhan Clock

Turns a Raspberry Pi into a self-hosted adhan clock that your whole family can
control from their phones. A single daemon (`adhand`) calculates prayer times
locally every day, plays the adhan at each prayer time, and serves a
phone-friendly web app on your home Wi-Fi — no cloud, no accounts, no ports
opened to the internet.

## Features

- **Web app for the whole family** — open `http://<pi-hostname>.local:8000` on
  any phone on the home network and "Add to Home Screen" for an app-like icon.
- **Automatic prayer times** — calculated on-device with the
  [praytimes.org](http://praytimes.org) engine; recomputed nightly and whenever
  settings change. Pick your calculation method, asr school, and high-latitude
  rule.
- **Per-prayer control** — enable/disable, volume, adhan audio, output device,
  a minute offset, an optional pre-adhan reminder chime, and a dua to play
  after the adhan.
- **Test anything** — preview any file, or simulate a reminder, the suhoor
  alarm, or a full adhan sequence, all with a chosen volume.
- **Live playback controls** — pause/resume, stop, and adjust volume of
  whatever is currently playing, right from the app.
- **Hooks** — run your own scripts before or after any prayer, filtered by day
  of week, with an optional schedule offset (e.g. Surah Al-Kahf 45 minutes
  before Friday dhuhr) and per-hook volume.
- **Ramadan mode** — Hijri date display, suhoor alarm, iftar countdown, and a
  Friday-dhuhr (jumu'ah) mode. Auto-detected from the Hijri calendar.
- **Bluetooth speakers** — scan, pair, and connect speakers from the app.
- **Health & self-update** — see CPU temp, uptime, disk, and version; pull the
  latest version and restart from a button in the app (no SSH needed).

## Hardware

1. A Raspberry Pi running Raspberry Pi OS (avoid the Pi Zero — no built-in audio
   out).
2. Speakers — **powered** speakers via the 3.5 mm jack, an HDMI display/speaker,
   a USB audio device, or a Bluetooth speaker. (The Pi's headphone jack is
   line-level and can't drive passive/unpowered speakers.)

## Install

Clone this repo into the `pi` user's home directory and run the installer:

```bash
cd ~
git clone <this-repo-url> raspberry-pi-adhan
cd raspberry-pi-adhan
./deploy/install.sh
```

The installer:

- installs system packages (`mpv`, `vlc`, `alsa-utils`, `bluez`),
- creates a Python virtualenv and installs dependencies,
- fetches a couple of dua recitations,
- installs and starts the `adhand` systemd service (auto-starts on boot),
- removes any leftover cron jobs from the older version of this project.

When it finishes, open `http://<pi-hostname>.local:8000` from any phone on your
Wi-Fi, set your location (the 📍 button uses the phone's GPS), and you're done.

## Usage

- **Set location & method** in the *Location & method* section, then Save.
- **Pick a speaker and volumes** per prayer in the *Prayers* section.
- **Add hooks** in the *Hooks* section — choose an installed script, the
  prayers and days it runs on, an offset, and a volume. Scripts live in
  `before-hooks.d/` and `after-hooks.d/`; only files placed there can be
  selected (the app can never run arbitrary commands).
- **Update** from the *System* section — it pulls this repo and restarts.

Logs: `journalctl -u adhand -f`

## Development

Runs on macOS/Linux for development (falls back to `mpv`/`afplay`, no ALSA
needed):

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000`. See [CLAUDE.md](CLAUDE.md) for architecture
notes and design decisions.

## Credits

- Prayer time calculation: <http://praytimes.org/code/>
- Original adhan-clock concept:
  <http://randomconsultant.blogspot.co.uk/2013/07/turn-your-raspberry-pi-into-azaanprayer.html>
- Dua recitations: [hisnmuslim.com](https://www.hisnmuslim.com) (Hisn al-Muslim)
