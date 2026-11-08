"""Seasonal deadlines for Community Center items (Amer's absolute rule: never miss a season).
Seasons come from the wiki infobox; fallback: the bundle source text / bundle name (bundles.json)."""
import json, os, re, subprocess
import needs
WIKI = os.environ.get("SV_WIKI", "")   # optional offline wiki CLI; the shipped JSON cache covers all standard bundle items
CACHE = os.path.join(os.path.dirname(__file__), "item_seasons.json")
SEASONS = ["spring", "summer", "fall", "winter"]

def _wiki(name):
    if not WIKI or not os.path.exists(WIKI): return {}
    out = subprocess.run(["python3", WIKI, "fields", name], capture_output=True, text=True).stdout
    f = {}
    for line in out.splitlines():
        m = re.match(r"(\w+)\s+(.*)", line)
        if m: f[m.group(1)] = m.group(2)
    return f

def _from_text(t):
    t = (t or "").lower()
    if "all" in re.findall(r"\b\w+\b", t): return list(SEASONS)
    return [s for s in SEASONS if s in t]

def item_info(names):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    src = {}
    for b, v in needs.B.items():
        for it in v["items"]:
            src.setdefault(it["name"], (it.get("source", ""), b))
    for n in names:
        if n in cache: continue
        f = _wiki(n)
        seasons = [s for s in _from_text(f.get("season", "").split(",")[0]) ]
        how = "wiki"
        if not seasons:
            s_text, bname = src.get(n, ("", ""))
            seasons = _from_text(s_text) or _from_text(bname)
            how = "bundle text" if seasons else "unknown (any season assumed)"
            seasons = seasons or list(SEASONS)
        g = re.match(r"(\d+)", f.get("growth", ""))
        cache[n] = {"seasons": seasons, "growth": int(g.group(1)) if g else None, "source": how}
    json.dump(cache, open(CACHE, "w"), indent=1)
    return cache

def missing_items(cc=None):
    cc = cc or needs.live()
    out = []
    for b in (cc or {}).get("bundles", []):
        if b["complete"] or b["room"] not in needs.ROOM_THRESHOLD: continue
        done = sum(g["done"] for g in b["ingredients"])
        if done >= b["slots"]: continue
        for g in b["ingredients"]:
            if not g["done"] and g["name"] != "Gold":
                out.append((g["name"], b["name"]))
    return out

def deadlines(season, day, cc=None):
    """URGENT: this season is the item's last chance in this year; crops: last planting day."""
    items = missing_items(cc)
    info = item_info({n for n, _ in items})
    si = SEASONS.index(season)
    urgent, soon = [], []
    # a bundle with free choice (e.g. 3 of 4) is only at risk if later seasons can't fill its slots
    cc = cc or needs.live()
    risk = {}
    for bb in (cc or {}).get("bundles", []):
        if bb["complete"]: continue
        miss = [g["name"] for g in bb["ingredients"] if not g["done"] and g["name"] != "Gold"]
        need = bb["slots"] - sum(g["done"] for g in bb["ingredients"])
        later_ok = [m for m in miss if any(SEASONS.index(x) > si for x in info.get(m, {"seasons": SEASONS})["seasons"])]
        risk[bb["name"]] = len(later_ok) < need
    for n, b in items:
        if not risk.get(b, True):
            av = [SEASONS.index(x) for x in info[n]["seasons"]]
            if si not in av and [x for x in av if x > si] and min(x for x in av if x > si) == si + 1:
                soon.append({"item": n, "bundle": b, "season": SEASONS[si + 1]})
            continue
        av = [SEASONS.index(s) for s in info[n]["seasons"]]
        later = [x for x in av if x > si]
        if si in av and not later:
            g = info[n]["growth"]
            last_plant = 28 - g if g else None
            urgent.append({"item": n, "bundle": b, "last_plant_day": last_plant, "days_left": 28 - day})
        elif si not in av and later and min(later) == si + 1:
            soon.append({"item": n, "bundle": b, "season": SEASONS[si + 1]})
    return urgent, soon
