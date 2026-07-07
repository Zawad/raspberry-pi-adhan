#!/usr/bin/env bash
# Dua after the adhan
#
# Plays the supplication recited after the adhan (Allahumma Rabba hadhihi
# ad-da'wati-t-tammah...) once the adhan finishes.
#
# To enable (in the web app): Hooks -> Add a hook
#   position: After adhan   script: 30-dua-after-adhan.sh
#   prayers:  all five      days:   every day
#
# Note: the app can also do this per prayer without a hook — each prayer's
# gear panel has an "After adhan" picker that plays a dua in-sequence. This
# hook is the one-rule-for-all-prayers alternative.
#
# Optional environment overrides:
#   DUA_FILE     audio file name   (default Dua-After-Adhan.mp3)
#   DUA_VOLUME   0-100             (default 70)
#   ADHAND_API   daemon API base   (default http://127.0.0.1:8000/api)

API="${ADHAND_API:-http://127.0.0.1:8000/api}"
FILE="${DUA_FILE:-Dua-After-Adhan.mp3}"
VOLUME="${HOOK_VOLUME:-${DUA_VOLUME:-70}}"

if [ "$1" != "--detached" ]; then
    nohup "$0" --detached >/dev/null 2>&1 &
    exit 0
fi

curl -s -X POST "$API/test" -H 'Content-Type: application/json' \
    -d "{\"mp3\": \"$FILE\", \"volume\": $VOLUME}" >/dev/null
