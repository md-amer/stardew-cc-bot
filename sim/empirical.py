"""Numbers measured from our own bot run (stats/events.jsonl, stats/day_summary.csv).
These are what OUR bot achieves, not what the game formula says a perfect player gets.
"""
import json, os, re, csv, collections, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "stats", "events.jsonl")
DS = os.path.join(ROOT, "stats", "day_summary.csv")
CAST = re.compile(r"cast (\d+): done(:\w+)? \[(.*?)\] \(bites (\d+) catches (\d+) escapes (\d+)\)")


def gmin(t):  # game time 1330 -> minutes since 0:00
    return (t // 100) * 60 + t % 100


def events():
    with open(EV) as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                pass


def fishing():
    """Per cast: what was caught, escapes, game minutes since previous cast in the same session."""
    caught = collections.Counter()
    by_loc = collections.defaultdict(collections.Counter)
    esc = 0
    bites = 0
    nocast = 0
    mins = []
    prev = None
    for e in events():
        m = CAST.search(e.get("msg", ""))
        if not m:
            continue
        n, flag, items, b, c, x = m.groups()
        n, b, c, x = int(n), int(b), int(c), int(x)
        key = (e["year"], e["season"], e["day"], e["loc"])
        if n == 0 or prev is None or prev[0] != key:
            pb = pc = px = 0
        else:
            pb, pc, px = prev[1:4]
            mins.append(gmin(e["time"]) - prev[4])
        if flag == ":no_cast":
            nocast += 1
        bites += b - pb
        esc += x - px
        for it in re.findall(r"'([^']+)'", items):
            caught[it] += 1
            by_loc[e["loc"]][it] += 1
        prev = (key, b, c, x, gmin(e["time"]))
    mins = [m for m in mins if 0 < m < 120]
    total_c = sum(caught.values())
    return {"casts_timed": len(mins),
            "game_min_per_cast_median": st.median(mins) if mins else None,
            "game_min_per_cast_mean": round(st.mean(mins), 1) if mins else None,
            "bites": bites, "items": total_c, "escapes": esc, "no_cast": nocast,
            "escape_rate": round(esc / max(1, bites), 3),
            "caught": caught.most_common(), "by_loc": {k: v.most_common(12) for k, v in by_loc.items()}}


def days():
    """Mean game minutes per activity per day, by season of year 1-3."""
    rows = list(csv.DictReader(open(DS)))
    cols = [c for c in rows[0] if c.startswith("min_")]
    out = {"days": len(rows), "real_s_per_day_median": st.median(int(r["real_s"]) for r in rows if r["real_s"])}
    for c in cols:
        out[c] = round(st.mean(int(r[c] or 0) for r in rows), 1)
    out["fails_per_day"] = round(st.mean(int(r["fails"] or 0) for r in rows), 2)
    return out


def walks():
    """'long walk ... (N tiles)' events: tiles per walk and how often."""
    pat = re.compile(r"long walk .*?\((\d+) tiles\)")
    n = [int(m.group(1)) for e in events() if (m := pat.search(e.get("msg", "")))]
    return {"long_walks": len(n), "median_tiles": st.median(n) if n else None}


if __name__ == "__main__":
    import sys
    print(json.dumps(globals()[sys.argv[1] if len(sys.argv) > 1 else "days"](), indent=1))
