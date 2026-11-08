#!/bin/bash
# Sample farmer position every 3 s into stats/pos_trace.csv (route analysis: wasted walks).
cd "$(dirname "$0")/.."
while true; do
  python3 -c "
import sys,time; sys.path.insert(0,'agent'); import sv
try:
    s=sv.call('state', observer=True); p=s['player']
    print(f\"{time.strftime('%H:%M:%S')},{s['season']},{s['day']},{s['time']},{p['loc']},{p['tile'][0]},{p['tile'][1]},{p['stamina']}\")
except Exception as e: pass" >> stats/pos_trace.csv
  sleep 3
done
