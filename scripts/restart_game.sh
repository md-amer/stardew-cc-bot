#!/bin/bash
# Restart the bot's isolated Stardew instance (own config dir = own Saves, own Mods). Your own game is untouched.
# Usage: restart_game.sh [--build] [--no-load]
set -e
source "$(dirname "$0")/common.sh"
cd "$ROOT"
G="$(find_game)" || { echo "Stardew Valley with SMAPI not found. Set STARDEW_PATH=/path/to/game"; exit 1; }
[ "$1" = "--build" ] && { scripts/deploy_mod.sh; shift; }
pkill -f "^./StardewModdingAPI --mods-path $ROOT/env/Mods" || true
sleep 2
mkdir -p env/config env/Mods logs
cat > env/run.sh <<EOS
#!/bin/bash
cd "$G"
export XDG_CONFIG_HOME="$ROOT/env/config" TERM=xterm
exec ./StardewModdingAPI --mods-path "$ROOT/env/Mods" > "$ROOT/env/smapi_console.log" 2>&1
EOS
chmod +x env/run.sh
if command -v hyprctl >/dev/null && [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ]; then
  hyprctl eval "hl.exec_cmd(\"$ROOT/env/run.sh\")" >/dev/null   # Hyprland: launch through the compositor
else
  setsid nohup env/run.sh >/dev/null 2>&1 &
fi
for i in $(seq 1 60); do sleep 1; curl -s -m 2 127.0.0.1:8775/ping >/dev/null && break; done
curl -s -m 2 127.0.0.1:8775/ping >/dev/null || { echo "mod API not answering; see env/smapi_console.log"; exit 1; }
[ "$1" = "--no-load" ] && exit 0
cd "$ROOT/agent" && python3 boot.py
