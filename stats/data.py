"""Stats data layer for the dashboard: events.jsonl (+ backfill from old day logs), RUNLOG.csv, live API."""
import csv, json, os, re, time, urllib.request
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, "stats", "events.jsonl")
BACKFILL = os.path.join(ROOT, "stats", "backfill.jsonl")
RUNLOG = os.path.join(ROOT, "RUNLOG.csv")
LOGS = os.path.join(ROOT, "logs")
API = "http://127.0.0.1:8775/"
SEASONS = ["spring", "summer", "fall", "winter"]

CATS = [  # (activity, regex on event message), first match wins
    ("fishing", r"cast \d+|fishing|fish spot"),
    ("mining", r"mine|lift to|descended"),
    ("farming", r"harvest|water|plant|cauliflower|replant|chop"),
    ("foraging", r"forag"),
    ("community", r"donat|CC:|Wizard|withdrew for bundles|bundle"),
    ("shopping", r"bought|backpack|shop"),
    ("chores", r"mail|shipped|stored|chest"),
    ("travel", r"path to warp|route|clearing a path"),
    ("sleep", r"going to sleep|NEW DAY"),
]
CAT_COLOR = {"fishing": "#4cc9f0", "mining": "#f77f00", "farming": "#80ed99", "foraging": "#c77dff",
             "community": "#ffd60a", "shopping": "#ff70a6", "chores": "#adb5bd", "travel": "#6c757d",
             "sleep": "#3a86ff", "other": "#495057"}


def category(msg):
    for name, rx in CATS:
        if re.search(rx, msg, re.I):
            return name
    return "other"


def day_index(season, day, year=1):
    return (year - 1) * 112 + SEASONS.index(season) * 28 + day


def minutes(t):
    return (t // 100) * 60 + t % 100 if t is not None else None


def backfill():
    """One-time: turn old text logs (before events.jsonl existed) into events. Snapshot fields partly empty."""
    if os.path.exists(BACKFILL):
        return
    rx = re.compile(r"^\[(\w+) (\d+) (\d+)\] (.*)$")
    rows = []
    for fn in sorted(os.listdir(LOGS)):
        m = re.match(r"y(\d+)_(\w+)_(\d+)\.log$", fn)
        if not m:
            continue
        money = None
        for line in open(os.path.join(LOGS, fn), errors="ignore"):
            g = rx.match(line.strip())
            if not g:
                continue
            season, day, t, msg = g.group(1), int(g.group(2)), int(g.group(3)), g.group(4)
            mm = re.search(r"money (\d+)", msg)
            if mm:
                money = int(mm.group(1))
            rows.append({"real": None, "year": int(m.group(1)), "season": season, "day": day, "time": t,
                         "money": money, "msg": msg, "backfill": True})
    with open(BACKFILL, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def load_events():
    backfill()
    out = []
    live_days = set()
    if os.path.exists(EVENTS):
        for line in open(EVENTS):
            try:
                e = json.loads(line)
                out.append(e)
                live_days.add((e.get("year"), e.get("season"), e.get("day")))
            except Exception:
                pass
    old = []
    for line in open(BACKFILL):
        e = json.loads(line)
        if (e["year"], e["season"], e["day"]) not in live_days:
            old.append(e)
    return old + out


def runlog_money():
    """Day -> last known money, from RUNLOG.csv (oldest days)."""
    m = {}
    if os.path.exists(RUNLOG):
        for r in csv.DictReader(open(RUNLOG)):
            try:
                y, s, d = r["date"].split()
                m[day_index(s, int(d), int(y[1:]))] = int(r["money"])
            except Exception:
                pass
    return m


def summarize(events):
    days = defaultdict(lambda: {"counts": Counter(), "minutes": Counter(), "fish": Counter(), "forage": Counter(),
                                "shipped": Counter(), "donated": [], "deepest": 0, "money_start": None, "money_end": None})
    totals = {"fish": Counter(), "forage": Counter(), "shipped": Counter(), "donated": [], "deepest": 0,
              "minutes": Counter(), "harvested": 0, "watered": 0, "planted": 0, "casts": 0, "bites": 0}
    prev = None
    for e in events:
        if e.get("season") not in SEASONS:
            continue
        k = day_index(e["season"], e["day"], e.get("year") or 1)
        d = days[k]
        msg = e.get("msg", "")
        cat = category(msg)
        d["counts"][cat] += 1
        if e.get("money") is not None:
            if d["money_start"] is None:
                d["money_start"] = e["money"]
            d["money_end"] = e["money"]
        # game minutes since the previous event (same day) belong to the activity that ended now
        if prev and prev[0] == k and e.get("time") and prev[1]:
            dt = minutes(e["time"]) - minutes(prev[1])
            if 0 < dt < 600:
                d["minutes"][cat] += dt; totals["minutes"][cat] += dt
        prev = (k, e.get("time"))
        m = re.match(r"cast \d+: (\S+) \[(.*?)\]", msg)
        if m:
            totals["casts"] += 1
            for name in re.findall(r"'([^']+)'", m.group(2)):
                d["fish"][name] += 1; totals["fish"][name] += 1
            if "caught" in m.group(1) or m.group(2):
                totals["bites"] += 1
        m = re.match(r"foraged (.+)", msg)
        if m:
            d["forage"][m.group(1)] += 1; totals["forage"][m.group(1)] += 1
        m = re.match(r"shipped (.+) x(\d+)", msg)
        if m:
            d["shipped"][m.group(1)] += int(m.group(2)); totals["shipped"][m.group(1)] += int(m.group(2))
        m = re.match(r"donated (.+) x(\d+) -> (.+)", msg)
        if m:
            d["donated"].append((m.group(1), m.group(3))); totals["donated"].append((m.group(1), m.group(3)))
        m = re.search(r"level (\d+)", msg)
        if m and "mine" in msg:
            lv = int(m.group(1)); d["deepest"] = max(d["deepest"], lv); totals["deepest"] = max(totals["deepest"], lv)
        for key in ("harvested", "watered"):
            m = re.match(key + r" (\d+)", msg)
            if m:
                totals[key] += int(m.group(1))
        m = re.match(r"planted .*?: (\d+)", msg)
        if m:
            totals["planted"] += int(m.group(1))
    return dict(days), totals


def money_series(days):
    rl = runlog_money()
    keys = sorted(set(days) | set(rl))
    out = []
    for k in keys:
        v = days.get(k, {}).get("money_end")
        out.append((k, v if v is not None else rl.get(k)))
    return [(k, v) for k, v in out if v is not None]


def api(cmd, timeout=0.4, **args):
    try:
        args["cmd"] = cmd; args["observer"] = True
        req = urllib.request.Request(API, data=json.dumps(args).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read())
            return j.get("data") if j.get("ok") else None
    except Exception:
        return None


_obs_ok = None
def live_ok():
    """Live API only when the mod honours observer=true (else polling would block auto-pause)."""
    global _obs_ok
    p = api("ping")
    _obs_ok = bool(p and p.get("observer"))
    return _obs_ok


CC_CACHE = os.path.join(ROOT, "stats", "cc.json")
def save_cc(cc):
    try: json.dump(cc, open(CC_CACHE, "w"))
    except Exception: pass
def load_cc():
    try: return json.load(open(CC_CACHE))
    except Exception: return None
