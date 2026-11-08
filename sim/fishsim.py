"""Monte Carlo of the game's fish pick (GameLocation.GetFishFromLocationData + CheckGenericFishRequirements,
SpawnFishData.GetChance). No bait, no lure, no tackle. Luck level 0. Daily luck given (default 0).

Simplifications (stated, not hidden):
- Entries with PlayerPosition/BobberPosition limits (legendaries, furniture spots) are skipped.
- Entries with player-state conditions (special orders, mail) are skipped; LOCATION_SEASON is evaluated.
- Mine fish (Ghostfish etc.) are decided by MineShaft code, not location data: not modelled here.
- No fish -> 'trash' (the game then gives trash/algae from its own code).
"""
import random, re, collections
import gamedata as g

FISH = g.fish()
SE = g.SEASONS


def _entries(loc):
    L = g.raw("Locations")
    out = []
    for r in (L["Default"].get("Fish") or []) + (L[loc].get("Fish") or []):
        if r.get("PlayerPosition") or r.get("BobberPosition"):
            continue
        iid = r.get("ItemId") or ""
        if not iid.startswith("(O)"):
            continue
        cond = r.get("Condition") or ""
        if "PLAYER_" in cond or "IS_PASSIVE_FESTIVAL" in cond:
            continue
        out.append(r)
    return out


def _cond_ok(cond, season, time):
    for part in [p.strip() for p in cond.split(",") if p.strip()]:
        m = re.match(r"(!?)LOCATION_SEASON Here (.*)", part)
        if m:
            ok = season in m.group(2).split()
            if ok == bool(m.group(1)):
                return False
            continue
        m = re.match(r"TIME (\d+) (\d+)", part)
        if m:
            if not int(m.group(1)) <= time <= int(m.group(2)):
                return False
    return True


def _generic_ok(fid, r, season, time, rain, level, depth, rng, luck):
    f = FISH.get(fid)
    if not f or f["trap"]:
        return True
    if r.get("IgnoreFishDataRequirements"):
        return True
    if not any(a <= time < b for a, b in f["times"]):
        return False
    if f["weather"] == "rainy" and not rain:
        return False
    if f["weather"] == "sunny" and rain:
        return False
    if level < f["min_level"]:
        return False
    w = f["spawn"]
    w -= max(0, f["maxdepth"] - depth) * (f["depth_mult"] * f["spawn"])
    w += level / 50
    w = min(w, 0.9)
    if r.get("ApplyDailyLuck"):
        w += luck
    return rng.random() < w


def cast(loc, season, time, rain, level=0, depth=4, area=None, rng=random, luck=0.0, caught=()):
    """One fish pick. Returns fish name or 'trash'."""
    s_i = SE.index(season)
    ents = _entries(loc)
    ents = sorted(ents, key=lambda r: (r.get("Precedence", 0), rng.random()))
    for r in ents:
        if r.get("FishAreaId") and r["FishAreaId"] != area:
            continue
        if "Season" in r and r["Season"] != s_i:
            continue
        if level < r.get("MinFishingLevel", 0):
            continue
        if depth < r.get("MinDistanceFromShore", 0):
            continue
        mx = r.get("MaxDistanceFromShore", -1)
        if mx > -1 and depth > mx:
            continue
        ch = r.get("Chance", 1.0) + (luck if r.get("ApplyDailyLuck") else 0)
        if rng.random() >= ch:
            continue
        if r.get("Condition") and not _cond_ok(r["Condition"], season, time):
            continue
        fid = r["ItemId"][3:]
        if r.get("CatchLimit", -1) > -1 and fid in caught:
            continue
        if _generic_ok(fid, r, season, time, rain, level, depth, rng, luck):
            return g.name(fid)
    return "trash"


def dist(loc, season, time, rain, level=0, depth=4, area=None, n=20000, seed=1):
    rng = random.Random(seed)
    c = collections.Counter(cast(loc, season, time, rain, level, depth, area, rng) for _ in range(n))
    return {k: v / n for k, v in c.most_common()}


if __name__ == "__main__":
    import sys, json
    a = sys.argv[1:]
    print(json.dumps(dist(a[0], a[1], int(a[2]), a[3] == "rain", int(a[4]), int(a[5]),
                          a[6] if len(a) > 6 and a[6] != "-" else None), indent=1))
