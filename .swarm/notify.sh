#!/usr/bin/env bash
# Usage: notify.sh <pane> <message>
# Sends a message to a tmux pane and submits it.
# Example: notify.sh main:0 "MSG_FROM_CLAUDE: done"
set -e
PANE="$1"
MSG="$2"
tmux send-keys -t "$PANE" "$MSG"
sleep 0.3
tmux send-keys -t "$PANE" "" Enter
