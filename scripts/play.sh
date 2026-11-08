#!/bin/bash
# Play N days autonomously (default 1). Each day: optional frame recording, play_day, optional timelapse.
# Stop cleanly: `touch agent/STOP` (finishes the current day, then exits). Never kill mid-day.
# agent/DONE (written when the Community Center is complete) ends the loop for good.
# A day whose runner exits without reaching the next day is NOT replayed: the loop stops.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/agent"
mkdir -p "$ROOT/logs"
N=${1:-1}
SPEED=${SPEED:-8}     # fair fast-forward: whole game update N times per frame (FastForward.cs)
RECORD=${RECORD:-0}   # 1 = save frames and encode a daily timelapse (needs ffmpeg)
rm -f STOP
day_key() { python3 -c "import sv; s=sv.state(); print('y%d_%s_%02d' % (s['year'], s['season'], s['day']))"; }
for i in $(seq 1 $N); do
  [ -f DONE ] && { echo "Community Center complete (agent/DONE): exiting"; break; }
  [ -f STOP ] && { echo "STOP file found, exiting"; rm -f STOP; break; }
  D=$(day_key)
  python3 -c "import sv; sv.call('speed', n=$SPEED)"
  [ "$RECORD" = 1 ] && python3 -c "import sv; sv.call('record', dir='$ROOT/media/frames/$D', every=2, div=2)"
  python3 -u -c "import play_day, act; act.run(play_day.main)" >> "$ROOT/logs/$D.log" 2>&1
  if [ "$RECORD" = 1 ]; then
    python3 -c "import sv; sv.call('record', dir=None)" 2>/dev/null
    ("$ROOT/scripts/encode_day.sh" $D >/dev/null 2>&1 &)
  fi
  python3 "$ROOT/scripts/day_summary.py" $D >/dev/null 2>&1
  if [ "$(day_key)" = "$D" ]; then
    echo "day $D did not end (runner killed or crashed); not replaying it" | tee -a "$ROOT/logs/$D.log"
    break
  fi
done
