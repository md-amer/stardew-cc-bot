"""Unlock graph: what locks what. Each node = something the farm can have/do.
Fields: req = list of requirement alternatives (any one inner list fully satisfied), d = days after reqs,
win = seasons in which the node can complete (None = any), note = source.
Earliest-day solver treats money and labour as free: it gives LOWER BOUNDS and the dependency structure.
Day index: 0 = Spring 1 Year 1. 112 days per year.
"""
SEASONS = ["spring", "summer", "fall", "winter"]

def season_of(t): return SEASONS[(t // 28) % 4]

N = {}
def node(name, req=None, d=0, win=None, note=""):
    if req is None: req = [[]]
    elif req and isinstance(req[0], str): req = [req]
    N[name] = dict(req=req, d=d, win=win, note=note)

# ---- tools, skills, access
node("start")
node("fishing rod", ["start"], 1, note="Willy gives Bamboo Pole Spring 2 (mail)")
node("mines open", ["start"], 4, note="Mines open Spring 5 (rockfall cleared)")
node("copper ore", ["mines open"])
node("furnace", ["copper ore"], note="Clint gives Furnace recipe after first copper ore (mail)")
node("copper bar", ["furnace"])
node("mine floor 20", ["mines open"], note="Ghostfish water, floor 20")
node("mine floor 40", ["mine floor 20"], note="Frozen Tear area, iron")
node("iron bar", ["mine floor 40", "furnace"])
node("mine floor 80", ["mine floor 40"], note="Fire Quartz area, gold")
node("gold bar", ["mine floor 80", "furnace"])
node("mine floor 120", ["mine floor 80"], note="Skull Key")
node("copper pickaxe", ["copper bar"], 2, note="Clint 2 days")
node("steel axe", ["iron bar"], 4, note="copper axe 2 d then steel axe 2 d; needed for large log to Secret Woods")
node("secret woods", ["steel axe"], note="Woodskip, Morel/Common mushroom, Fiddlehead, hardwood stumps")
node("hardwood x10", [["copper axe"], ["secret woods"]], note="stumps need copper axe")
node("copper axe", ["copper bar"], 2)
node("fishing 3", ["fishing rod"], 4, note="XP; crab pot recipe + Willy sells crab pot")
node("crab pot", ["fishing 3"])
node("farming 2", ["start"], 10, note="sprinkler, mayo")
node("sprinkler", ["farming 2", "copper bar", "iron bar"])
node("farming 6", ["start"], 40, note="cheese press, quality sprinkler")
node("foraging 4", ["start"], 20, note="tapper")
node("tapper", ["foraging 4", "copper bar"])
node("earned 25000", ["start"], 30, note="placeholder: real date from simulator")
node("fruit bats", ["earned 25000"], 1, note="Demetrius event after 25,000g earned")
node("rusty key (sewer)", ["start"], 200, note="60 museum donations: late")

# ---- buildings / animals (money ignored here)
node("coop", ["start"], 3); node("big coop", ["coop"], 2); node("deluxe coop", ["big coop"], 2)
node("chickens adult", ["coop"], 3)
node("large egg (white)", ["chickens adult"], 12, note="friendship 200 then ~50%/day: median 15 d after purchase")
node("large egg (brown)", ["chickens adult"], 12)
node("duck", ["big coop"]); node("duck egg", ["duck"], 5 + 2)
node("duck feather", ["duck"], 22, note="median 22 d (95% 44)")
node("rabbit", ["deluxe coop"]); node("wool", ["rabbit"], 6 + 4)
node("rabbit's foot", ["rabbit"], 27, note="median 27 d (95% 63)")
node("barn", ["start"], 3); node("cow", ["barn"]); node("milk pail", ["start"])
node("large milk", ["cow", "milk pail"], 15)
node("milk", ["cow", "milk pail"], 6)
node("big barn", ["barn"], 2); node("goat", ["big barn"]); node("goat milk large", ["goat"], 16)
node("deluxe barn", ["big barn"], 2); node("pig", ["deluxe barn"]); node("truffle", ["pig"], 11, win=["spring", "summer", "fall"], note="pig adult 10 d; no truffles in winter")
node("truffle oil", ["truffle", "oil maker"], 1)
node("oil maker", ["farming 8"]); node("farming 8", ["start"], 60)
node("house upgrade", ["start"], 3, note="kitchen: Fried Egg")

# ---- machines from bundle rewards OR skills
node("bee house", [["farming 3"], ["B:Fall Crops"]]); node("farming 3", ["start"], 18)
node("honey", ["bee house"], 4, win=["spring", "summer", "fall"])
node("preserves jar", [["farming 4"], ["B:Quality Crops"]]); node("farming 4", ["start"], 25)
node("jelly", ["preserves jar", "any fruit"], 3)
node("cheese press", [["farming 6"], ["B:Animal"]]); node("cheese", ["cheese press", "milk"], 1)
node("goat cheese", ["cheese press", "goat milk large"], 1)
node("loom", ["farming 7"]); node("farming 7", ["start"], 50)
node("cloth", [["loom", "wool"], ["recycling machine", "fishing rod"]], 2, note="loom; or soggy newspaper 10%")
node("recycling machine", [["fishing 4"], ["B:Field Research"]]); node("fishing 4", ["fishing rod"], 6)
node("keg", [["farming 8"], ["B:Artisan"]]); node("wine", ["keg", "any fruit"], 7)
node("any fruit", [["fruit bats"], ["apple tree"], ["cherry tree"], ["apricot tree"]])
node("apple tree", ["start"], 28, win=["fall"], note="sapling 4000g, 28 d, fruits in fall")
node("apricot tree", ["start"], 28, win=["spring"]); node("cherry tree", ["start"], 28, win=["spring"])
node("orange tree", ["start"], 28, win=["summer"]); node("peach tree", ["start"], 28, win=["summer"])
node("pomegranate tree", ["start"], 28, win=["fall"])

# ---- room unlocks
node("greenhouse", ["R:Pantry"], 1); node("bus (desert)", ["R:Vault"], 1)
node("minecarts", ["R:Boiler Room"], 1); node("quarry", ["R:Crafts Room"], 1)
node("glittering boulder (pan)", ["R:Fish Tank"], 1)
node("tide pools (bridge 300 wood)", ["start"], note="Beach east: Sea Urchin, Coral")

# ---- items with season windows (forage, fish, crops)
SEAS = lambda *s: list(s)
def crop(name, grow, seasons, extra_req=None):
    node(name, ["start"] + (extra_req or []), grow, win=seasons, note=f"crop {grow} d")
for nm, gd, ss in [("Parsnip", 4, ["spring"]), ("Green Bean", 10, ["spring"]), ("Cauliflower", 12, ["spring"]),
                   ("Potato", 6, ["spring"]), ("Tomato", 11, ["summer"]), ("Hot Pepper", 5, ["summer"]),
                   ("Blueberry", 13, ["summer"]), ("Melon", 12, ["summer"]), ("Corn", 14, ["summer", "fall"]),
                   ("Eggplant", 5, ["fall"]), ("Pumpkin", 13, ["fall"]), ("Yam", 10, ["fall"]),
                   ("Wheat", 4, ["summer", "fall"]), ("Sunflower", 8, ["summer", "fall"]), ("Poppy", 7, ["summer"])]:
    crop(nm, gd, ss)
node("Red Cabbage", [["cart luck"], ["year 2"]], 9, win=["summer"], note="Pierre Y2 only; cart ~6%/visit")
node("cart luck", ["start"], 40, note="placeholder expected wait"); node("year 2", ["start"], 112)
node("gold Corn x5", ["Corn"], 8, win=["summer", "fall"]); node("gold Pumpkin x5", ["Pumpkin"], 0, win=["fall"])
node("gold Melon x5", ["Melon"], 0, win=["summer"]); node("gold Parsnip x5", ["Parsnip"], 0, win=["spring"])
F = {  # forage
 "Wild Horseradish": ["spring"], "Daffodil": ["spring"], "Leek": ["spring"], "Dandelion": ["spring"],
 "Spice Berry": ["summer"], "Grape": ["summer"], "Sweet Pea": ["summer"],
 "Common Mushroom": ["fall"], "Wild Plum": ["fall"], "Hazelnut": ["fall"], "Blackberry": ["fall"],
 "Winter Root": ["winter"], "Crystal Fruit": ["winter"], "Snow Yam": ["winter"], "Crocus": ["winter"],
 "Fiddlehead Fern": ["summer"], "Morel": ["spring"], "Red Mushroom": ["summer", "fall"],
 "Clam": None, "Cockle": None, "Mussel": None, "Oyster": None, "Nautilus Shell": ["winter"],
}
for k, w in F.items():
    node(k, ["secret woods"] if k in ("Fiddlehead Fern", "Morel") else ["start"], 0, win=w, note="forage")
node("Spice Berry (bats)", ["fruit bats"]); node("Wild Plum (bats)", ["fruit bats"]); node("Blackberry (bats)", ["fruit bats"])
node("Sea Urchin", ["tide pools (bridge 300 wood)"]); node("Purple Mushroom", [["mine floor 80"], ["fruit bats_no"]], note="floor 81+ or mushroom cave")
node("Maple Syrup", ["tapper"], 9); node("Oak Resin", ["tapper"], 7); node("Pine Tar", ["tapper"], 5)
node("Coconut", ["bus (desert)"]); node("Cactus Fruit", ["bus (desert)"]); node("Cave Carrot", ["mines open"])
FISH = {"Sunfish": ["spring", "summer"], "Catfish": ["spring", "fall", "winter"], "Shad": ["spring", "summer", "fall"],
        "Tiger Trout": ["fall", "winter"], "Largemouth Bass": None, "Carp": None, "Bullhead": None,
        "Sturgeon": ["summer", "winter"], "Sardine": ["spring", "fall", "winter"], "Tuna": ["summer", "winter"],
        "Red Snapper": ["summer", "fall", "winter"], "Tilapia": ["summer", "fall"], "Walleye": ["fall", "winter"],
        "Bream": None, "Eel": ["spring", "fall"], "Pufferfish": ["summer"], "Chub": None}
for k, w in FISH.items(): node(k, ["fishing rod"], 0, win=w, note="fish")
node("Woodskip", ["secret woods", "fishing rod"]); node("Ghostfish", ["mine floor 20", "fishing rod"])
node("Sandfish", ["bus (desert)", "fishing rod"])
node("Lobster/Crab/Shrimp etc", ["crab pot"], 1)
node("Quartz", ["mines open"]); node("Earth Crystal", ["mines open"]); node("Frozen Tear", ["mine floor 40"])
node("Fire Quartz", ["mine floor 80"]); node("Aquamarine", ["mine floor 40"]); node("Frozen Geode", ["mine floor 40"])
node("Slime x99", ["mines open"]); node("Bat Wing x10", ["mine floor 40"]); node("Solar Essence", ["mine floor 40"])
node("Void Essence", ["mine floor 80"])
node("Maki Roll", ["start"], note="Gus 300g daily"); node("Fried Egg", [["house upgrade", "chickens adult"], ["cart luck"]])
node("Poppy item", ["Poppy"]); node("Hay x10", ["start"], note="Marnie 50g")
node("Wood/Stone", ["start"]); node("Duck Feather", ["duck feather"])

# ---- bundles (choose the cheapest k of n handled by solver: list all options + need)
B = {
 "Spring Crops": (4, ["Parsnip", "Green Bean", "Cauliflower", "Potato"], "Pantry"),
 "Summer Crops": (4, ["Tomato", "Hot Pepper", "Blueberry", "Melon"], "Pantry"),
 "Fall Crops": (4, ["Corn", "Eggplant", "Pumpkin", "Yam"], "Pantry"),
 "Quality Crops": (3, ["gold Parsnip x5", "gold Melon x5", "gold Pumpkin x5", "gold Corn x5"], "Pantry"),
 "Animal": (5, ["large milk", "large egg (white)", "large egg (brown)", "goat milk large", "wool", "duck egg"], "Pantry"),
 "Artisan": (6, ["truffle oil", "cloth", "goat cheese", "cheese", "honey", "jelly", "apple tree", "apricot tree",
                 "orange tree", "peach tree", "pomegranate tree", "cherry tree"], "Pantry"),
 "Spring Foraging": (4, ["Wild Horseradish", "Daffodil", "Leek", "Dandelion"], "Crafts Room"),
 "Summer Foraging": (3, ["Spice Berry", "Grape", "Sweet Pea"], "Crafts Room"),
 "Fall Foraging": (4, ["Common Mushroom", "Wild Plum", "Hazelnut", "Blackberry"], "Crafts Room"),
 "Winter Foraging": (4, ["Winter Root", "Crystal Fruit", "Snow Yam", "Crocus"], "Crafts Room"),
 "Construction": (1, ["Wood/Stone"], "Crafts Room"),  # hardwood handled below
 "Exotic Foraging": (5, ["Coconut", "Cactus Fruit", "Cave Carrot", "Red Mushroom", "Purple Mushroom", "Maple Syrup",
                         "Oak Resin", "Pine Tar", "Morel"], "Crafts Room"),
 "River Fish": (4, ["Sunfish", "Catfish", "Shad", "Tiger Trout"], "Fish Tank"),
 "Lake Fish": (4, ["Largemouth Bass", "Carp", "Bullhead", "Sturgeon"], "Fish Tank"),
 "Ocean Fish": (4, ["Sardine", "Tuna", "Red Snapper", "Tilapia"], "Fish Tank"),
 "Night Fishing": (3, ["Walleye", "Bream", "Eel"], "Fish Tank"),
 "Specialty Fish": (4, ["Pufferfish", "Ghostfish", "Sandfish", "Woodskip"], "Fish Tank"),
 "Crab Pot": (5, ["Clam", "Cockle", "Mussel", "Oyster", "Lobster/Crab/Shrimp etc"], "Fish Tank"),
 "Blacksmith's": (3, ["copper bar", "iron bar", "gold bar"], "Boiler Room"),
 "Geologist's": (4, ["Quartz", "Earth Crystal", "Frozen Tear", "Fire Quartz"], "Boiler Room"),
 "Adventurer's": (2, ["Slime x99", "Bat Wing x10", "Solar Essence", "Void Essence"], "Boiler Room"),
 "Vault": (1, ["start"], "Vault"),
 "Chef's": (6, ["Maple Syrup", "Fiddlehead Fern", "truffle", "Poppy item", "Maki Roll", "Fried Egg"], "Bulletin Board"),
 "Field Research": (4, ["Purple Mushroom", "Nautilus Shell", "Chub", "Frozen Geode"], "Bulletin Board"),
 "Enchanter's": (4, ["Oak Resin", "wine", "rabbit's foot", "pomegranate tree"], "Bulletin Board"),
 "Dye": (6, ["Red Mushroom", "Sea Urchin", "Sunflower", "Duck Feather", "Aquamarine", "Red Cabbage"], "Bulletin Board"),
 "Fodder": (3, ["Wheat", "Hay x10", "apple tree"], "Bulletin Board"),
}
B["Construction"] = (2, ["Wood/Stone", "hardwood x10"], "Crafts Room")
ROOMS = {}
for b, (k, items, room) in B.items():
    ROOMS.setdefault(room, []).append(b)


def earliest(overrides=None):
    """Fixed-point earliest day per node (bundles: k-th smallest of their options). Lower bounds."""
    T = {"start": 0}
    if overrides: T.update(overrides)
    INF = 10**6
    def fit(t, win):
        if win is None: return t
        for x in range(t, t + 113):
            if season_of(x) in win: return x
        return INF
    for _ in range(60):
        changed = False
        for n, v in N.items():
            if n in (overrides or {}) or n == "start": continue
            best = INF
            for alt in v["req"]:
                tt = max([T.get(r, INF) if not r.startswith(("B:", "R:")) else T.get(r, INF) for r in alt] or [0])
                if tt < INF:
                    # crops/seasonal: the whole grow must sit in-window -> start must be in window too
                    t0 = tt
                    if v["win"] and v["d"] > 0 and v["note"].startswith("crop"):
                        while True:
                            s = fit(t0, v["win"])
                            if s >= INF: break
                            if all(season_of(x) in v["win"] for x in range(s, s + v["d"] + 1)):
                                best = min(best, s + v["d"]); break
                            t0 = s + 1
                    else:
                        best = min(best, fit(tt + v["d"], v["win"]))
            if best < T.get(n, INF):
                T[n] = best; changed = True
        for b, (k, items, room) in B.items():
            ts = sorted(T.get(i, INF) for i in items)
            t = ts[k - 1] if len(ts) >= k else INF
            if t < T.get("B:" + b, INF): T["B:" + b] = t; changed = True
        for room, bs in ROOMS.items():
            t = max(T.get("B:" + b, INF) for b in bs)
            if t < T.get("R:" + room, INF): T["R:" + room] = t; changed = True
        if not changed: break
    return T


def date(t):
    if t >= 10**6: return "never"
    return f"Y{t // 112 + 1} {SEASONS[(t // 28) % 4]} {t % 28 + 1}"


def critical(T, target):
    """Walk back the binding requirement chain."""
    chain = [target]; cur = target
    while True:
        if cur.startswith("R:"):
            room = cur[2:]; cur = max(("B:" + b for b in ROOMS[room]), key=lambda x: T.get(x, 0))
        elif cur.startswith("B:"):
            k, items, _ = B[cur[2:]]; cur = sorted(items, key=lambda i: T.get(i, 0))[k - 1]
        elif cur in N:
            alts = N[cur]["req"]
            best = min(alts, key=lambda a: max([T.get(r, 0) for r in a] or [0]))
            if not best or best == ["start"]: break
            cur = max(best, key=lambda r: T.get(r, 0))
        else: break
        chain.append(cur)
        if cur == "start" or len(chain) > 30: break
    return chain


if __name__ == "__main__":
    T = earliest()
    print("LOWER BOUND dates (money, labour free; skills placeholders):")
    for b in B: print(f"  {b:16} {date(T['B:' + b]):18}")
    for r in ROOMS: print(f"ROOM {r:16} {date(T['R:' + r])}")
    allr = max(T["R:" + r] for r in ROOMS); print("CC complete lower bound:", date(allr))
    last = max(ROOMS, key=lambda r: T["R:" + r])
    print("critical chain:", " <- ".join(f"{c} [{date(T.get(c, 0))}]" for c in critical(T, "R:" + last)))
