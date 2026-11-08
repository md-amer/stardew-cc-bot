"""Load the raw game data dump (sim/data/game/*.json, from tools/datadump) into
compact planning tables. Every number here comes from the game's own Content/Data
files (v1.6.15, GOG). Nothing is typed in by hand.

Note: the dump drops fields equal to their C# default (0, false, null), so a
missing int field means 0.
"""
import json, os, re
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "game")
SEASONS = ["spring", "summer", "fall", "winter"]


@lru_cache(None)
def raw(name):
    with open(os.path.join(RAW, f"Data_{name}.json")) as f:
        return json.load(f)


def obj(item_id):
    """Object record for '24', '(O)24' etc."""
    i = str(item_id).replace("(O)", "")
    return raw("Objects").get(i)


def name(item_id):
    s = str(item_id)
    if s.startswith("(BC)"):
        r = raw("BigCraftables").get(s[4:])
        return r["Name"] if r else s
    o = obj(s)
    return o["Name"] if o else s


@lru_cache(None)
def id_by_name():
    return {v["Name"]: k for k, v in raw("Objects").items()}


# ---------------------------------------------------------------- bundles
def bundles():
    """Standard (non-remixed) bundles. Each: room, id, name, items[(id,name,qty,quality)],
    need (slots to fill), reward."""
    out = []
    for key, val in raw("Bundles").items():
        room, bid = key.split("/")
        parts = val.split("/")
        bname, reward, items = parts[0], parts[1], parts[2].split()
        need = int(parts[4]) if len(parts) > 4 and parts[4] else None
        its = []
        for i in range(0, len(items), 3):
            iid, qty, q = items[i], int(items[i + 1]), int(items[i + 2])
            its.append({"id": iid, "name": "gold" if iid == "-1" else name(iid), "qty": qty, "quality": q})
        out.append({"room": room, "id": int(bid), "name": bname, "items": its,
                    "need": need or len(its), "reward": reward})
    return out


# ---------------------------------------------------------------- crops
@lru_cache(None)
def crops():
    """seed id -> crop facts, plus Pierre/Joja seed price (shop price, after markup)."""
    pierre = shop_prices("SeedShop")
    joja = shop_prices("Joja")
    out = {}
    for seed, c in raw("Crops").items():
        h = c["HarvestItemId"]
        ho = obj(h) or {}
        so = obj(seed) or {}
        out[seed] = {
            "seed": so.get("Name", seed), "crop": ho.get("Name", h), "crop_id": h,
            "seasons": [SEASONS[s] for s in c.get("Seasons", [0])] if c.get("Seasons") else ["spring"],
            "phases": c["DaysInPhase"], "grow_days": sum(c["DaysInPhase"]),
            "regrow": c.get("RegrowDays", -1),
            "trellis": c.get("IsRaised", False),
            "water": c.get("NeedsWatering", False),
            "min_stack": c.get("HarvestMinStack", 1), "max_stack": c.get("HarvestMaxStack", 1),
            "extra_chance": c.get("ExtraHarvestChance", 0.0),
            "sell": ho.get("Price", 0), "seed_sell": so.get("Price", 0),
            "pierre": pierre.get(seed), "joja": joja.get(seed),
        }
    return out


# ---------------------------------------------------------------- shops
# Object.salePrice(ignoreProfitMargins) special cases: (Y1 price, Y2+ price)
YEAR_PRICES = {"(O)388": (10, 50), "(O)390": (20, 100), "(O)382": (120, 250),
               "(O)378": (80, 160), "(O)380": (150, 250), "(O)384": (350, 750)}


def sale_price(iid, price, year=1, quality=0):
    """Shop base price when ShopItemData.Price is -1 (Object.cs salePrice)."""
    if iid in YEAR_PRICES:
        return YEAR_PRICES[iid][0 if year <= 1 else 1]
    return int(price * 2 * (1 + quality * 0.25))


def shop_items(shop, year=1):
    s = raw("Shops")[shop]
    mods = s.get("PriceModifiers") or []
    res = []
    for it in s.get("Items") or []:
        iid = it.get("ItemId") or it.get("Id")
        base = it.get("Price", -1)
        if base in (-1, None):
            o = obj(iid) if iid and iid.startswith("(O)") else None
            base = sale_price(iid, o["Price"], year) if o else None
        if base is not None and not it.get("IgnoreShopPriceModifiers"):
            for m in mods:  # Modification 2 = Multiply
                if m.get("Modification") == 2:
                    base = base * m["Amount"]
        if base is not None:
            base = int(base)
        res.append({"id": iid, "name": name(iid) if iid else iid, "price": base,
                    "cond": it.get("Condition"), "stock": it.get("AvailableStock", -1),
                    "trade": it.get("TradeItemId"), "trade_qty": it.get("TradeItemAmount")})
    return res


def shop_prices(shop, year=1):
    return {str(i["id"]).replace("(O)", ""): i["price"] for i in shop_items(shop, year) if i["id"]}


# ---------------------------------------------------------------- fish
FISH_FIELDS = "name difficulty behavior minsize maxsize times seasons weather locations_unused maxdepth spawnmult depthmult minlevel tutorial".split()


@lru_cache(None)
def fish():
    """Data/Fish rows. Normal fish: times [(start,end)], seasons, weather, difficulty.
    Trap (crab pot) rows: chance, location type."""
    out = {}
    for fid, row in raw("Fish").items():
        p = row.split("/")
        if p[1] == "trap":
            out[fid] = {"name": p[0], "trap": True, "chance": float(p[2]), "water": p[4]}
            continue
        t = p[5].split()
        out[fid] = {"name": p[0], "trap": False, "difficulty": int(p[1]), "behavior": p[2],
                    "times": [(int(t[i]), int(t[i + 1])) for i in range(0, len(t), 2)],
                    "seasons": p[6].split(), "weather": p[7], "maxdepth": int(p[9]),
                    "spawn": float(p[10]), "depth_mult": float(p[11]), "min_level": int(p[12])}
    return out


def location_fish(loc):
    """Fish list for a location (own + Default inherited)."""
    L = raw("Locations")
    rows = list(L[loc].get("Fish") or [])
    rows += [r for r in L["Default"].get("Fish") or [] if r.get("CanBeInherited")]
    out = []
    for r in rows:
        iid = r.get("ItemId") or r.get("Id")
        out.append({"id": iid, "name": name(iid) if iid else None, "chance": r.get("Chance", 1.0),
                    "season": SEASONS[r["Season"]] if "Season" in r else None,
                    "area": r.get("FishAreaId"), "cond": r.get("Condition"),
                    "min_level": r.get("MinFishingLevel", 0), "precedence": r.get("Precedence", 0)})
    return out


def location_forage(loc):
    L = raw("Locations")[loc]
    return {"spawn_min": L.get("MinDailyForageSpawn"), "spawn_max": L.get("MaxDailyForageSpawn"),
            "max_at_once": L.get("MaxSpawnedForageAtOnce"),
            "items": [{"name": name(r["ItemId"]), "id": r["ItemId"], "season": SEASONS[r["Season"]] if "Season" in r else None,
                       "chance": r.get("Chance", 1.0)} for r in L.get("Forage") or []]}


# ---------------------------------------------------------------- machines
def machines():
    out = {}
    for mid, m in raw("Machines").items():
        rules = []
        for r in m.get("OutputRules") or []:
            trig = [t.get("RequiredItemId") or t.get("RequiredTags") for t in r.get("Triggers") or []]
            outs = [o.get("ItemId") for o in r.get("OutputItem") or []]
            rules.append({"in": trig, "out": outs, "minutes": r.get("MinutesUntilReady"),
                          "days": r.get("DaysUntilReady")})
        out[name(mid)] = rules
    return out


if __name__ == "__main__":
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else "bundles"
    print(json.dumps(globals()[what](*sys.argv[2:]), indent=1))
