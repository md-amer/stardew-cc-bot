#!/bin/bash
# Shared helpers: project root and Stardew Valley install detection.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
find_game() {
  # STARDEW_PATH wins; then common Steam and GOG install folders. Needs SMAPI installed in that folder.
  local c
  for c in "$STARDEW_PATH" \
      "$HOME/.local/share/Steam/steamapps/common/Stardew Valley" \
      "$HOME/.steam/steam/steamapps/common/Stardew Valley" \
      "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Stardew Valley" \
      "$HOME/GOG Games/Stardew Valley/game" \
      "$HOME/Games/Stardew Valley/game" "$HOME/Games/stardew-valley/game"; do
    [ -n "$c" ] && [ -x "$c/StardewModdingAPI" ] && { echo "$c"; return 0; }
  done
  return 1
}
