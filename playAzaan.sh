#!/usr/bin/env bash
echo "Start of playAzaan.sh"

if [ $# -lt 1 ]; then
  echo "USAGE: $0 <azaan-audio-path> [<volume>]"
  exit 1
fi

audio_path="$1"
vol=${2:-0}
root_dir=`dirname $0`

echo "audio path $audio_path, vol $vol, root_dir $root_dir"

# Run before hooks
for hook in $root_dir/before-hooks.d/*; do
    echo "Running before hook: $hook"
    $hook
done

# Debug
# Print the user ID
echo "User ID: $(id -u)" >> $root_dir/debug.log

# Print the username
echo "Username: $(whoami)" >> $root_dir/debug.log

# Print the home directory
echo "Home Directory: $HOME" >> $root_dir/debug.log

# Print the cron environment variables
echo "Cron Environment: $(printenv)" >> $root_dir/debug.log

# Play Azaan audio
cvlc --no-dbus --play-and-exit --gain $vol $audio_path

# Run after hooks
for hook in $root_dir/after-hooks.d/*; do
    echo "Running after hook: $hook"
    $hook
done