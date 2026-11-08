#!/bin/bash
# Build ClaudeHands and copy it into the isolated agent Mods folder (never the user's Mods folder).
set -e
source "$(dirname "$0")/common.sh"; cd "$ROOT"
G="$(find_game)" && GP="-p:GamePath=$G"
dotnet build -c Release "$GP" mod/ClaudeHands 2>&1 | grep -E " error |rror\(s\)" | sort -u
mkdir -p env/Mods/ClaudeHands
cp mod/ClaudeHands/bin/Release/net6.0/ClaudeHands.dll mod/ClaudeHands/manifest.json env/Mods/ClaudeHands/
