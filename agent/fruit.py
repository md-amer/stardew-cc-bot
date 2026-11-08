"""Fall fruit trees for the CC (session 6, Su 17 Y2): Fodder needs 3 Apples, Enchanter's needs 1 Pomegranate.

Wiki (Fruit Trees, Apple Sapling, Pomegranate Sapling, Pierre's General Store):
- Apple Sapling 4,000g, Pomegranate Sapling 6,000g at Pierre. 28 days to mature, then 1 fruit per day in season (fall).
- Planted on untilled ground. While growing, the 8 surrounding tiles must stay empty (debris or objects there stop
  growth for that night).
Deadline: a sapling planted on summer day D matures on fall day D, so 3 Apples by Fa 28 needs D <= 25 and one
Pomegranate needs D <= 27. Later = Fall Y3.
"""
import sv, act, town

SAPLINGS = [("Apple", "Apple Sapling", 4000, 25), ("Pomegranate", "Pomegranate Sapling", 6000, 27)]


def _prog():
    import play_day
    return play_day.prog()


def _save(p):
    import play_day
    play_day.save_prog(p)


def wanted():
    """Saplings still needed: bundle wants the fruit and no tree of ours is planted for it."""
    import needs
    q = needs.quota()
    planted = _prog().get("fruit_trees", {})
    return [(f, sap, cost, last) for f, sap, cost, last in SAPLINGS if f in q and f not in planted]


def _spot():
    """Center of a 3x3 of diggable ground holding only clearable stuff (grass, weeds, stones, twigs).
    Su 21 Y2: zero fully empty 3x3 blocks on the farm (summer grass), so clear one like a player would."""
    act.goto("Farm", 64, 24)
    dig = {(t["x"], t["y"]) for t in sv.call("tile_prop", layer="Back", prop="Diggable")}
    a = sv.call("around", r=90)
    objs = {(o["x"], o["y"]): o["name"] for o in a["objects"]}
    feats = {(f["x"], f["y"]): f["type"] for f in a["features"]}
    hard = set()
    for c in a["clumps"]:
        for dx in range(c["w"]):
            for dy in range(c["h"]): hard.add((c["x"] + dx, c["y"] + dy))
    for b in a.get("buildings", []):
        for dx in range(-1, b.get("w", 0) + 1):
            for dy in range(-1, b.get("h", 0) + 2): hard.add((b["x"] + dx, b["y"] + dy))
    def ok(t):
        if t not in dig or t in hard: return False
        o = objs.get(t)
        if o and not any(k in o for k in ("Weeds", "Stone", "Twig")): return False
        f = feats.get(t)
        return f in (None, "Grass")
    taken = [tuple(v) for v in _prog().get("fruit_trees", {}).values()] + [(74, 14), (75, 14)]
    dirt = [t for t, f in feats.items() if f == "HoeDirt"]
    best = None
    for (x, y) in dig:
        if any(abs(x - a_) <= 3 and abs(y - b_) <= 3 for a_, b_ in taken): continue
        if not all(ok((x + dx, y + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)): continue
        if any(abs(x - a_) <= 2 and abs(y - b_) <= 2 for a_, b_ in dirt): continue    # keep field paths open
        # decompiled FruitTree.IsTooCloseToAnotherTree: no Tree/FruitTree within 2 tiles (5x5), else placement fails
        if any(feats.get((x + dx, y + dy)) in ("Tree", "FruitTree") for dx in range(-2, 3) for dy in range(-2, 3)): continue
        n_clear = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (x + dx, y + dy) in objs)
        d = abs(x - 64) + abs(y - 24)
        key = (n_clear, d)
        if best is None or key < best[0]: best = (key, x, y)
    if not best: return None
    x, y = best[1], best[2]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            t = (x + dx, y + dy); o = objs.get(t)
            if not o: continue                       # grass may stay (decompiled IsGrowthBlocked allows Grass)
            tool = "Pickaxe" if "Stone" in o else "Axe" if "Twig" in o else "Scythe"
            act.walk(t[0], t[1], adjacent=True)
            try: act.use(t[0], t[1], tool=tool)
            except Exception as e: act.log(f"FRUIT: clearing {t}: {e!r}")
    act.log(f"FRUIT: spot {(x, y)} cleared ({best[0][0]} tiles)")
    return (x, y)


def buy_and_plant():
    s = sv.state()
    if s["season"] != "summer" or s["time"] >= 1600 or (s["day"] - 1) % 7 == 2:   # Pierre 9-17, closed Wednesday
        return
    # Su 21 Y2: bought both, planting failed (no spot): plant saplings already carried, never buy twice
    held = [w for w in wanted() if act.slot_of(w[1]) is not None]
    if held:
        _plant(held, s); return
    todo = [w for w in wanted() if s["day"] <= w[3]]
    for f, sap, cost, last in wanted():
        if s["day"] > last:
            act.log(f"FRUIT: too late for {sap} this year (deadline Su {last}); {f} slips to Fall Y3 or the cart")
    if not todo:
        return
    money = s["player"]["money"]
    # Amer: sell to Pierre for instant money. Value of sellable backpack goods counts toward the price.
    sell_val = sum(i.get("price", 0) * i["stack"] for i in act.inv() if i.get("cat") in town.PIERRE_CATS)
    afford = [w for w in todo if w[2] <= money + sell_val]
    if not afford:
        act.log(f"FRUIT: need {todo[0][2]}g for {todo[0][1]} by Su {todo[0][3]}, have {money}g + {sell_val}g goods")
        return
    buy = []
    for w in afford:
        if sum(b[2] for b in buy) + w[2] <= money + sell_val:
            buy.append(w)
    import play_day
    if s.get("backpack", 12) - len(act.inv()) < len(buy) + 1 and money >= sum(b[2] for b in buy):
        play_day.chest_sync_and_ship()        # selling frees slots; otherwise make room first
    town.open_shop("SeedShop")
    need = sum(b[2] for b in buy)
    if money < need:
        town.sell_until(need)
        money = sv.state()["player"]["money"]
        while buy and sum(b[2] for b in buy) > money: buy.pop()
        if not buy:
            act.log(f"FRUIT: still short after selling ({money}g)"); town.close_menu(); return
    town.buy({sap: 1 for _, sap, _, _ in buy})
    town.close_menu()
    _plant(buy, s)


def _plant(buy, s):
    for f, sap, cost, last in buy:
        if act.slot_of(sap) is None:
            act.log(f"FRUIT: {sap} not in backpack after buying"); continue
        spot = _spot()
        if not spot:
            act.log("FRUIT: no clearable 3x3 spot on the farm"); return
        act.walk(*spot, adjacent=True)
        try: act.use(*spot, tool="Scythe")        # Su 22 Y2: grass ON the tile blocks placement (neighbours may keep it)
        except Exception: pass
        act.use(*spot, tool=sap)
        if act.slot_of(sap) is None:
            p = _prog(); p.setdefault("fruit_trees", {})[f] = list(spot); _save(p)
            act.log(f"FRUIT: planted {sap} at {spot} (Su {s['day']}, fruit from Fa {s['day']})")
        else:
            act.log(f"FRUIT: planting {sap} at {spot} failed")


def keep_clear():
    """Every morning: clear debris from the 3x3 around each growing sapling (else it does not grow that night)."""
    trees = _prog().get("fruit_trees", {})
    if not trees:
        return
    a = None
    for f, (x, y) in trees.items():
        if a is None:
            act.goto("Farm"); a = sv.call("around", r=80)
        for o in a["objects"]:
            if abs(o["x"] - x) <= 1 and abs(o["y"] - y) <= 1 and (o["x"], o["y"]) != (x, y):
                n = o["name"]
                tool = "Pickaxe" if "Stone" in n else "Axe" if n in ("Twig", "Stump") else "Scythe"
                act.walk(o["x"], o["y"], adjacent=True)
                try:
                    act.use(o["x"], o["y"], tool=tool)
                    act.log(f"FRUIT: cleared {n} next to the {f} sapling")
                except Exception as e:
                    act.log(f"FRUIT: could not clear {n} at {(o['x'], o['y'])}: {e!r}")


def pick():
    """Decompiled FruitTree.performUseAction: right-click (action) shakes the tree and drops its fruit. Never the Axe."""
    import farming, needs
    trees = _prog().get("fruit_trees", {})
    q = set(needs.quota())
    s = sv.state()
    if s["season"] != "fall" or not any(f in q for f in trees): return
    for f, (x, y) in trees.items():
        if f not in q: continue
        n0 = sum(i["stack"] for i in act.inv() if i["name"] == f)
        if act.walk(x, y, adjacent=True) != "arrived":
            act.log(f"FRUIT: cannot reach the {f} tree at {(x, y)}"); continue
        act.use(x, y, right=True)      # right-click = action (shake), with the Axe in hand so no food gets eaten
        import time as _t; _t.sleep(0.5)
        farming.collect_debris(r=4)
        n1 = sum(i["stack"] for i in act.inv() if i["name"] == f)
        act.log(f"FRUIT: shook the {f} tree: {f} {n0} -> {n1}")
