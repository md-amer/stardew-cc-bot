"""Derived planning tables, computed from game data with the decompiled formulas.
Run: python3 tables.py  -> writes data/tables.json and prints a summary.
"""
import json, os
import gamedata as g

HERE = os.path.dirname(os.path.abspath(__file__))
SE = g.SEASONS
FORAGE_LOCS = ["Forest", "Town", "Mountain", "Beach", "BusStop", "Backwoods", "Railroad", "Woods", "Desert"]


def forage():
    """Per location and season: daily spawn count range and P(item | one spawn).
    GameLocation.spawnObjects: pick a forage entry uniformly, keep it with its Chance,
    so P(item) = chance_i / sum(chance) among entries valid that season (Default + location)."""
    dflt = g.raw("Locations")["Default"].get("Forage") or []
    out = {}
    for loc in FORAGE_LOCS:
        L = g.raw("Locations")[loc]
        rows = dflt + (L.get("Forage") or [])
        for s_i, s in enumerate(SE):
            valid = [r for r in rows if r.get("Season", s_i) == s_i]
            tot = sum(r.get("Chance", 1.0) for r in valid)
            if not tot:
                continue
            p = {}
            for r in valid:
                n = g.name(r["ItemId"])
                p[n] = p.get(n, 0) + r.get("Chance", 1.0) / tot
            out.setdefault(loc, {})[s] = {
                "spawn_min": L.get("MinDailyForageSpawn"), "spawn_max": L.get("MaxDailyForageSpawn"),
                "max_at_once": L.get("MaxSpawnedForageAtOnce"),
                "p_item": {k: round(v, 4) for k, v in sorted(p.items(), key=lambda x: -x[1])}}
    return out


def crab_pot():
    """CrabPot.DayUpdate: 20% junk (10% with Deluxe Bait), else walk Data/Fish trap rows in file order,
    each rolls its chance; first hit wins; no hit -> junk."""
    fish = g.fish()
    out = {}
    for water in ["ocean", "freshwater"]:
        for bait in ["none", "deluxe"]:
            junk = 0.2 if bait == "none" else 0.1
            left = 1 - junk
            dist = {}
            for fid, f in fish.items():
                if not f["trap"] or water not in f["water"].split():
                    continue
                dist[f["name"]] = left * f["chance"]
                left *= 1 - f["chance"]
            dist["junk"] = junk + left
            out[f"{water}/{bait}"] = {k: round(v, 4) for k, v in dist.items()}
    return out


def cart():
    """Travelling Cart (Fri, Sun): 10 objects drawn uniformly from the eligible pool (ItemQueryResolver.RANDOM_ITEMS
    + Traveler PerItemCondition). Price = max(random 100..1000 step 100, base x 3/4/5)."""
    O = g.raw("Objects")
    pool = []
    for k, o in O.items():
        if not k.isdigit() or not 2 <= int(k) <= 789:
            continue
        if o.get("Category", 0) in (0, -999) or o.get("Type") in ("Quest", "Minerals", "Arch"):
            continue
        if o.get("Price", 0) <= 0 or o.get("ExcludeFromRandomSale"):
            continue
        pool.append((o["Name"], o["Price"]))
    n = len(pool)
    p_visit = 10 / n
    return {"pool": n, "p_item_per_visit": round(p_visit, 4),
            "p_item_per_season_8_visits": round(1 - (1 - p_visit) ** 8, 3),
            "price_rule": "max(U{100..1000}, base x U{3,4,5})",
            "items": {nm: pr for nm, pr in pool}}


def geodes():
    """Utility.getTreasureFromGeode: 50% mineral list (12 equal), else resource branch where 1/4 of 50%
    is the geode's bundle mineral. P(Earth Crystal | Geode) = 0.5 x 0.5 x 0.25 = 6.25% (same for Frozen Tear
    from Frozen Geode, Fire Quartz from Magma Geode; Omni: 2.08% each of the three)."""
    return {"Geode": {"Earth Crystal": 0.0625, "Stone": 0.125, "Clay": 0.0625, "each_mineral": 0.5 / 12},
            "Frozen Geode": {"Frozen Tear": 0.0625, "each_mineral": 0.5 / 12},
            "Magma Geode": {"Fire Quartz": 0.0625, "each_mineral": 0.5 / 12},
            "Omni Geode": {"Fire Quartz": 0.0625 / 3, "Frozen Tear": 0.0625 / 3, "Earth Crystal": 0.0625 / 3}}


def mine_floor_items():
    """MineShaft.getRandomItemForThisLevel (crystals lying on the floor): 25% area mineral, else Quartz.
    Floors 1-39: Earth Crystal; 40-79: Frozen Tear; 80-119: Fire Quartz. (10% Purple Mushroom above
    floor 20 outside 40-79 is checked first; 5% Purple? no: 420=Red Mushroom, 422=Purple Mushroom > floor 80.)"""
    return {"1-39": {"Earth Crystal": 0.25, "Quartz": 0.75},
            "40-79": {"Frozen Tear": 0.25, "Quartz": 0.75},
            "80-119": {"Fire Quartz": 0.25, "Quartz": 0.75},
            "21-39,80+": {"Red Mushroom first roll": 0.10}, "81+": {"Purple Mushroom first roll": 0.05}}


def crops_table():
    rows = {}
    for seed, c in g.crops().items():
        if not (c["pierre"] or c["joja"]):
            continue
        days = c["grow_days"]
        harvests = lambda left: 0 if left < days else (1 + (left - days) // c["regrow"] if c["regrow"] > 0 else left // days)
        rows[c["crop"]] = {"seasons": c["seasons"], "grow": days, "regrow": c["regrow"], "seed_pierre": c["pierre"],
                           "seed_joja": c["joja"], "sell": c["sell"], "trellis": c["trellis"],
                           "latest_plant_day": {s: 28 - days for s in c["seasons"]},  # plant by day X, harvest by 28
                           "harvests_from_day1": harvests(27)}
    return rows


def all_tables():
    return {"forage": forage(), "crab_pot": crab_pot(), "cart": cart(), "geodes": geodes(),
            "mine_floor_items": mine_floor_items(), "crops": crops_table(),
            "bundles": g.bundles(), "fish": g.fish(), "machines": g.machines()}


if __name__ == "__main__":
    t = all_tables()
    json.dump(t, open(os.path.join(HERE, "data", "tables.json"), "w"), indent=1)
    print("crab pot", json.dumps(t["crab_pot"], indent=0))
    c = t["cart"]; c2 = dict(c); c2.pop("items"); print("cart", c2)
    for loc in ["Forest", "Mountain", "Town", "Beach", "BusStop"]:
        for s, v in t["forage"].get(loc, {}).items():
            print(loc, s, v["spawn_min"], "-", v["spawn_max"], "max", v["max_at_once"], v["p_item"])
