#!/bin/bash
# One-time setup: checks requirements, builds the ClaudeHands mod into a private Mods folder,
# and installs the `stardew-cc` command. Your own saves and Mods folder are never touched.
set -e
source "$(dirname "$0")/scripts/common.sh"
cd "$ROOT"
ok() { echo "  ok: $*"; }
die() { echo "  MISSING: $*"; exit 1; }
echo "Checking requirements..."
command -v python3 >/dev/null && ok "python3" || die "python3"
command -v dotnet >/dev/null && ok "dotnet ($(dotnet --version))" || die ".NET SDK 6+ (https://dotnet.microsoft.com/download)"
command -v curl >/dev/null && ok "curl" || die "curl"
G="$(find_game)" && ok "Stardew Valley + SMAPI: $G" || die "Stardew Valley with SMAPI (https://smapi.io). Or set STARDEW_PATH=/path/to/game"
echo "Building the mod..."
scripts/deploy_mod.sh
mkdir -p env/config logs stats media "$HOME/.local/bin"
ln -sf "$ROOT/scripts/stardew-cc" "$HOME/.local/bin/stardew-cc"
echo
echo "Done. Run:  stardew-cc        (stop early: stardew-cc stop)"
echo "Make sure ~/.local/bin is on your PATH."
