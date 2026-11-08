"""Fish planner from wiki facts (location, hours, season, weather), cached in fish_wiki.json.
Picks the map where the most still-needed bundle fish can bite right now."""
import json, os, re, subprocess
WIKI = os.environ.get("SV_WIKI", "")   # optional offline wiki CLI; the shipped JSON cache covers all standard bundle items
CACHE = os.path.join(os.path.dirname(__file__), "fish_wiki.json")
# wiki location -> maps the agent can fish (river: Town first; the Forest river banks gave shore casts)
MAPS = {"River": ["Town", "Forest"], "Mountain Lake": ["Mountain"], "Ocean": ["Beach"], "Forest Pond": ["Forest"]}

def _fields(name):
    if not WIKI or not os.path.exists(WIKI): return {}
    out = subprocess.run(["python3", WIKI, "fields", name], capture_output=True, text=True).stdout
    f = {}
    for line in out.splitlines():
        m = re.match(r"(\w+)\s+(.*)", line)
        if m: f[m.group(1)] = m.group(2)
    return f

def _hour(tok):
    m = re.match(r"(\d+)(am|pm)", tok.strip().lower())
    h = int(m.group(1)) % 12 + (12 if m.group(2) == "pm" else 0)
    return h if h >= 6 else h + 24          # 12am..2am = 24..26 (game clock runs past midnight)

def facts(names):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    for n in names:
        if n in cache: continue
        f = _fields(n)
        if "location" not in f:
            cache[n] = None; continue
        windows = []
        for part in re.split(r"[•,]", f.get("time", "")):
            ts = re.findall(r"\d+(?:am|pm)", part.lower())
            if len(ts) == 2: windows.append((_hour(ts[0]), _hour(ts[1])))
        w = f.get("weather", "Any")
        cache[n] = {"locations": [l.strip() for l in f["location"].split("•")],
                    "windows": windows or [(6, 26)],
                    "seasons": [x.strip().lower() for x in re.split(r"[•,]", f.get("season", "All"))],
                    "weather": "rain" if "Rain" in w and "Sun" not in w else ("sun" if "Sun" in w and "Rain" not in w else "any")}
    json.dump(cache, open(CACHE, "w"), indent=1)
    return cache

def biting(fact, season, weather, time):
    if not fact: return False
    ss = [s.split()[0] for s in fact["seasons"] if s]            # "winter, with rain totem" -> "winter"
    if "all" not in ss and season not in ss: return False
    wet = weather in ("rain", "storm")
    if fact["weather"] == "rain" and not wet: return False
    if fact["weather"] == "sun" and wet: return False
    h = time // 100 + (time % 100) / 60
    return any(a <= h < b for a, b in fact["windows"])

def plan(needed_fish, season, weather, time, exclude=()):
    """[(map, [fish...])] best first. needed_fish: names still missing from bundles."""
    f = facts(needed_fish)
    score = {}
    for n in needed_fish:
        if not biting(f.get(n), season, weather, time): continue
        for loc in f[n]["locations"]:
            for m in MAPS.get(loc, []):
                if m not in exclude:
                    score.setdefault(m, []).append(n)
                    break                     # one map per location (first = preferred)
    return sorted(score.items(), key=lambda kv: -len(kv[1]))
