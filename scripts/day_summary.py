#!/usr/bin/env python3
"""Per-day analysis row -> stats/day_summary.csv (Amer: keep detailed stats for later analysis).
Reads logs/<day>.log and stats/pos_trace.csv. Columns: game-time spent per activity, long walks,
failures, real seconds for the day, money start/end, bundles done.
Usage: day_summary.py y1_fall_23   (or no argument: every log)."""
import csv, os, re, sys, glob
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stats"))
from data import category

def mins(t):
    t = int(t); return (t // 100) * 60 + t % 100

def summarise(day):
    path = os.path.join(ROOT, "logs", day + ".log")
    lines = [l for l in open(path, errors="replace") if re.match(r"\[\w+ \d+ \d+\]", l)]
    # keep only the last attempt of the day (restarts repeat DAY START)
    starts = [i for i, l in enumerate(lines) if "=== DAY START" in l]
    if starts: lines = lines[starts[-1]:]
    spent, prev = Counter(), None
    fails = longw = 0; money0 = money1 = None
    for l in lines:
        m = re.match(r"\[(\w+) (\d+) (\d+)\] (.*)", l)
        t, msg = mins(m.group(3)), m.group(4)
        if prev: spent[category(prev[1])] += max(0, t - prev[0])
        prev = (t, msg)
        fails += "FAILED" in msg or "failed" in msg
        longw += msg.startswith("long walk")
        mm = re.search(r"money (\d+)", msg)
        if mm:
            money0 = money0 or int(mm.group(1)); money1 = int(mm.group(1))
    real = None
    tr = os.path.join(ROOT, "stats", "pos_trace.csv")
    if os.path.exists(tr):
        season, d = day.split("_")[1], str(int(day.split("_")[2]))
        rows = [r for r in csv.reader(open(tr)) if len(r) > 3 and r[1] == season and r[2] == d]
        if rows:
            h = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8])
            real = (h(rows[-1][0]) - h(rows[0][0])) % 86400
    row = {"day": day, "real_s": real, "money_start": money0, "money_end": money1, "fails": fails, "long_walks": longw}
    for k in ("farming", "fishing", "mining", "foraging", "community", "shopping", "chores", "travel", "sleep", "other"):
        row["min_" + k] = spent.get(k, 0)
    return row

if __name__ == "__main__":
    days = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, "logs", "y*_*.log")))
    out = os.path.join(ROOT, "stats", "day_summary.csv")
    old = {r["day"]: r for r in csv.DictReader(open(out))} if os.path.exists(out) else {}
    for d in days:
        try: old[d] = summarise(d)
        except Exception as e: print(d, e)
    keys = list(next(iter(old.values())).keys())
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader()
        order = {"spring": 0, "summer": 1, "fall": 2, "winter": 3}
        for d in sorted(old, key=lambda k: (k.split("_")[0], order.get(k.split("_")[1], 9), int(k.split("_")[2]))):
            w.writerow({k: old[d].get(k) for k in keys})
    print(f"{len(old)} days -> {out}")
