#!/usr/bin/env bash
# Friday morning Surah Al-Kahf
#
# The Prophet ﷺ encouraged reciting Surah Al-Kahf on Fridays. This hook asks
# the adhan daemon to play a recitation after the fajr adhan finishes, filling
# the house with Quran as everyone starts the blessed day.
#
# To enable (in the web app): Hooks -> Add a hook. Two good recipes:
#
#   Early morning:   position: After adhan    prayers: fajr    days: Fri
#   Pre-Jummah:      position: Before adhan   prayers: dhuhr   days: Fri
#                    offset: -45  (starts 45 min before the dhuhr adhan)
#
# (The script appears in both catalogs; before-hooks.d/ holds a symlink.)
#
# Playback goes through the daemon's API, so the app's chosen speaker,
# now-playing status, and Stop button all still work. The script detaches
# immediately, so the adhan flow is never delayed.
#
# Optional environment overrides (set in the systemd unit if desired):
#   KAHF_FILE            audio file name        (default Al-Khaf-Mishary-Rashid.mp3)
#   KAHF_VOLUME          0-100                  (default 60)
#   KAHF_DELAY_MINUTES   wait before starting (default 0) — prefer the hook's
#                        offset setting in the app instead
#   ADHAND_API           daemon API base        (default http://127.0.0.1:8000/api)

API="${ADHAND_API:-http://127.0.0.1:8000/api}"
FILE="${KAHF_FILE:-Al-Khaf-Mishary-Rashid.mp3}"
VOLUME="${HOOK_VOLUME:-${KAHF_VOLUME:-60}}"
DELAY_MINUTES="${KAHF_DELAY_MINUTES:-0}"

if [ "$1" != "--detached" ]; then
    nohup "$0" --detached >/dev/null 2>&1 &
    exit 0
fi

sleep "$((DELAY_MINUTES * 60))"
curl -s -X POST "$API/test" -H 'Content-Type: application/json' \
    -d "{\"mp3\": \"$FILE\", \"volume\": $VOLUME}" >/dev/null
