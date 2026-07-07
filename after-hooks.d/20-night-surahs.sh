#!/usr/bin/env bash
# Night routine: Surah Al-Mulk then Surah As-Sajdah
#
# The Prophet ﷺ would not sleep until he had recited Surah Al-Mulk and Surah
# As-Sajdah, and said Al-Mulk intercedes for its companion until they are
# forgiven. This hook plays both, back to back, after the isha adhan sequence
# finishes — a winding-down "night mode" for the household.
#
# To enable (in the web app): Hooks -> Add a hook
#   position: After adhan   script: 20-night-surahs.sh
#   prayers:  isha          days:   every day (or your pick)
#
# Playback goes through the daemon's API (speaker choice, now-playing, and the
# Stop button keep working; pressing Stop also cancels the second surah). The
# script detaches immediately, so the adhan flow is never delayed.
#
# Optional environment overrides:
#   NIGHT_SURAH_1   first audio file    (default Al-Mulk-Mishary-Rashid.mp3)
#   NIGHT_SURAH_2   second audio file   (default As-Sajdah-Mishary-Rashid.mp3)
#   NIGHT_VOLUME    0-100               (default 50)
#   ADHAND_API      daemon API base     (default http://127.0.0.1:8000/api)

API="${ADHAND_API:-http://127.0.0.1:8000/api}"
SURAH_1="${NIGHT_SURAH_1:-Al-Mulk-Mishary-Rashid.mp3}"
SURAH_2="${NIGHT_SURAH_2:-As-Sajdah-Mishary-Rashid.mp3}"
VOLUME="${NIGHT_VOLUME:-50}"

if [ "$1" != "--detached" ]; then
    nohup "$0" --detached >/dev/null 2>&1 &
    exit 0
fi

play() {
    curl -s -X POST "$API/test" -H 'Content-Type: application/json' \
        -d "{\"mp3\": \"$1\", \"volume\": $VOLUME}" >/dev/null
}

# poll until the player is idle (up to ~40 min, covers the longest surah)
wait_idle() {
    for _ in $(seq 1 480); do
        curl -s "$API/status" | grep -q '"playing":null' && return 0
        sleep 5
    done
    return 1
}

play "$SURAH_1"
sleep 3
wait_idle || exit 0          # something else is playing forever; bow out
# if the user pressed Stop during surah 1 (latest event), skip surah 2 too
curl -s "$API/events?limit=1" | grep -q '"type": *"stopped"' && exit 0
play "$SURAH_2"
