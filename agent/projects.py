"""Farm buildings and machines (recipes from the wiki):
- Furnace: 25 Stone + 20 Copper Ore. Copper Bar = 5 Copper Ore + 1 Coal, 30 min (Blacksmith's bundle, sprinklers).
- Scarecrow: 50 Wood + 1 Coal + 20 Fiber; protects crops within 8 tiles (crows above 15 crops).
Positions are saved in progress.json."""
import time
import sv, act, farming, craft, donate

CHEST = (74, 14)

def _prog():
    import play_day; return play_day.prog()

def _save(p):
    import play_day; play_day.save_prog(p)

def have(name):
    return sum(i["stack"] for i in act.inv() if i["name"] == name)

def free_tile_near(cx, cy, r=6, avoid=()):
    """Nearest tile that is walkable, empty (no object, no terrain feature) and leaves its neighbours walkable."""
    g = sv.call("grid")["rows"]
    objs, feats, blocked = farming.tile_info(r=r + 4)
    best = None
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if not (0 <= y < len(g) and 0 <= x < len(g[0])) or g[y][x] != ".": continue
            if (x, y) in objs or (x, y) in feats or (x, y) in blocked or (x, y) in avoid: continue
            if sum(1 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)) if 0 <= y+dy < len(g) and 0 <= x+dx < len(g[0]) and g[y+dy][x+dx] == ".") < 3: continue
            d = abs(x - cx) + abs(y - cy)
            if best is None or d < best[0]: best = (d, x, y)
    return best and (best[1], best[2])

def placed_ok(name, t):
    objs, _, _ = farming.tile_info(r=3)
    o = objs.get(tuple(t))
    return bool(o and o["name"] == name)

N_FURNACES = 2

def furnaces():
    p = _prog()
    fs = [tuple(t) for t in p.get("furnaces", [])]
    if p.get("furnace") and tuple(p["furnace"]) not in fs: fs.insert(0, tuple(p["furnace"]))
    return fs

def furnace():
    act.goto("Farm")
    fs = furnaces()
    if len(fs) < N_FURNACES:
        if have("Copper Ore") < 25 or have("Stone") < 25:
            donate.withdraw_bundle_items({"Copper Ore", "Stone", "Coal"})
        if have("Copper Ore") >= 30 and have("Stone") >= 25 and craft.craft("Furnace") >= 1 and act.slot_of("Furnace") is not None:
            t = free_tile_near(CHEST[0] - 3, CHEST[1] + 1, avoid={CHEST} | set(fs))
            craft.place("Furnace", *t)
            if placed_ok("Furnace", t):
                p = _prog(); p["furnaces"] = [list(x) for x in fs + [t]]; _save(p); act.log(f"furnace placed at {t}")
            else:
                act.log(f"furnace: place at {t} failed")
    smelt()

def smelt():
    fs = furnaces()
    if not fs: return
    act.goto("Farm", fs[0][0], fs[0][1] + 2, adjacent=True)     # tile_info scans around the farmer
    for t in fs:
        objs, _, _ = farming.tile_info(r=14)
        o = objs.get(t)
        if not o:
            act.log(f"furnace missing at {t}"); continue
        if o.get("ready"):
            act.walk(*t, adjacent=True); act.use(*t, right=True); time.sleep(0.4)
            act.log(f"furnace: collected, bars: Copper {have('Copper Bar')} Iron {have('Iron Bar')} Gold {have('Gold Bar')}")
        elif o.get("busy"):
            continue
        if have("Coal") < 1 or not any(have(x) >= 5 for x in ("Gold Ore", "Iron Ore", "Copper Ore")):
            donate.withdraw_bundle_items({"Copper Ore", "Coal", "Iron Ore", "Gold Ore"})
        for ore in ("Gold Ore", "Iron Ore", "Copper Ore"):
            if have(ore) >= 5 and have("Coal") >= 1:
                n0 = have(ore)
                act.walk(*t, adjacent=True); act.use(*t, tool=ore, right=True); time.sleep(0.4)
                act.log(f"furnace {t}: " + ("smelting " + ore if have(ore) < n0 else ore + " not accepted (busy?)"))
                break

def buy_ores():
    """Wiki (Blacksmith stock, Year 1): Iron Ore 150g, Gold Ore 400g, Coal 150g. 5 ore + 1 coal = 1 bar.
    Blacksmith's bundle needs 1 Copper, 1 Iron, 1 Gold Bar."""
    import needs, town
    s = sv.state()
    q = needs.quota()
    want = {}
    ch = _prog().get("chest", {})
    for bar, ore in (("Iron Bar", "Iron Ore"), ("Gold Bar", "Gold Ore")):
        if bar in q and have(bar) + ch.get(bar, 0) == 0 and have(ore) + ch.get(ore, 0) < 5:
            want[ore] = 5 - have(ore) - ch.get(ore, 0)
    # Steel Axe needs 5 Iron Bars (+1 for the bundle) once the Copper Axe is in hand
    if axe_tier() == 1 and "Fiddlehead Fern" in q and s["season"] == "summer" and s["day"] <= 25:
        bars = have("Iron Bar") + ch.get("Iron Bar", 0) - (1 if "Iron Bar" in q else 0)
        need_ore = max(0, (5 - bars) * 5 - have("Iron Ore") - ch.get("Iron Ore", 0))
        if need_ore: want["Iron Ore"] = want.get("Iron Ore", 0) + need_ore
    if jar_wanted() and have("Coal") + ch.get("Coal", 0) < 8:
        want["Coal"] = 8 - have("Coal") - ch.get("Coal", 0)      # Preserves Jar: 8 Coal
    need_coal = sum(want.get(o, 0) for o in ("Iron Ore", "Gold Ore")) // 5 + 1
    if want and have("Coal") + ch.get("Coal", 0) < need_coal:
        want["Coal"] = need_coal - have("Coal") - ch.get("Coal", 0)
    if not want or not (900 <= s["time"] < 1400) or (s["day"] - 1) % 7 == 4:
        return
    cost = sum(n * (400 if o == "Gold Ore" else 150) for o, n in want.items())
    if s["player"]["money"] < cost + 800:
        return
    act.goto("Blacksmith")
    c = counter("Blacksmith", "Clint")
    if not c: return
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if resp:
        sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(1.0)       # first option = Shop
    if (sv.state().get("menu") or {}).get("type") != "ShopMenu":
        act.log(f"buy_ores: shop did not open ({sv.state().get('menu')})"); town.close_menu(); return
    time.sleep(0.6); town._last_shop = None
    town.buy(want)
    town.close_menu()
    act.log(f"buy_ores: wanted {want}; now Iron Ore {have('Iron Ore')} Gold Ore {have('Gold Ore')}")

def scarecrow():
    p = _prog()
    if p.get("scarecrow") and not p.get("chest", {}).get("Scarecrow"): return
    import os
    if os.path.exists(os.path.join(os.path.dirname(__file__), "SCARECROW_OFF")):
        return                                   # crafted scarecrows vanished twice (Su 2, Su 3): debugging
    act.goto("Farm", 64, 20)
    _, feats, _ = farming.tile_info(r=30)
    crops = [t for t, f in feats.items() if f["type"] == "HoeDirt" and "crop" in f and not f.get("dead")]
    if len(crops) < 16 or sv.state()["time"] >= 1700: return
    if p.get("chest", {}).get("Scarecrow") and not have("Scarecrow"):
        donate.withdraw_bundle_items({"Scarecrow"})
    if have("Scarecrow"):
        return _place_scarecrow(crops)
    if have("Wood") < 50 or have("Coal") < 1 or have("Fiber") < 20:
        donate.withdraw_bundle_items({"Wood", "Coal", "Fiber"})
    if have("Fiber") < 20:
        act.log(f"scarecrow: fiber {have('Fiber')}, cutting weeds")
        cut_weeds(20)
    if have("Wood") < 50:
        farming.chop_trees(wood_target=50, min_stamina=60)
    if have("Wood") < 50 or have("Fiber") < 20 or have("Coal") < 1:
        act.log(f"scarecrow: missing wood {have('Wood')} fiber {have('Fiber')} coal {have('Coal')}"); return
    if craft.craft("Scarecrow") < 1 or act.slot_of("Scarecrow") is None:
        act.log("scarecrow: craft failed"); return
    _place_scarecrow(crops)

def _place_scarecrow(crops):
    """Place every held Scarecrow: first at the crop centroid, then at the centroid of crops still uncovered."""
    placed = [tuple(t) for t in (_prog().get("scarecrows") or [])]
    while have("Scarecrow"):
        left = [c for c in crops if all((c[0]-t[0])**2 + (c[1]-t[1])**2 > 64 for t in placed)]
        if len(left) < 6: break
        cx = round(sum(x for x, _ in left) / len(left)); cy = round(sum(y for _, y in left) / len(left))
        t = free_tile_near(cx, cy, r=8, avoid=set(placed))
        n0 = have("Scarecrow")
        craft.place("Scarecrow", *t)
        if placed_ok("Scarecrow", t):
            placed.append(t)
            p = _prog(); p["scarecrow"] = list(placed[0]); p["scarecrows"] = [list(x) for x in placed]; _save(p)
            act.log(f"scarecrow placed at {t}")
        else:
            st = sv.state()
            act.log(f"scarecrow: place at {t} failed (held {have('Scarecrow')}/{n0}, me {st['player']['tile']}, tool {st.get('tool')})")
            break
    left = [c for c in crops if all((c[0]-t[0])**2 + (c[1]-t[1])**2 > 64 for t in placed)]
    if placed: act.log(f"scarecrows {placed}; {len(left)} crops uncovered")

def cut_weeds(target, r=30):
    """Weeds drop Fiber when cut (wiki: Fiber)."""
    for _ in range(40):
        st = sv.state()
        if have("Fiber") >= target or st["player"]["stamina"] < 60 or st["time"] >= 1700: break
        objs, _, _ = farming.tile_info(r=r)
        _, me = act.here()
        w = sorted((t for t, o in objs.items() if o["name"] == "Weeds"), key=lambda t: abs(t[0]-me[0]) + abs(t[1]-me[1]))
        if not w: act.log("no weeds left nearby"); break
        if farming.approach(w[0]) == "arrived":
            act.use(*w[0], tool="Scythe")
        farming.collect_debris(r=3)

def run():
    if sv.state()["time"] >= 1800:
        act.log("projects: too late today"); return
    # farm-local steps first (chest withdrawals), town errands after: Fa 23 walked Clint -> chest -> town again
    def silo():                # morning slot: the animals step runs after Robin's window on spring days (Sp 1)
        import animals; animals.build_silo()
    for step in (farm_cave, tappers, keg, jelly, scarecrow, stumps, furnace, silo, upgrade_axe, upgrade_pickaxe, buy_ores, geodes, vault, buy_wood, buy_hay, buy_rod):
        try: step()
        except Exception as e:
            import traceback; act.log(f"projects.{step.__name__} failed: {e!r} @ {traceback.format_exc().splitlines()[-3].strip()}")
            try:
                import town; town.close_menu()
            except Exception: pass

def counter(keyword, npc):
    """Shop counter tile with Action containing keyword; several may exist: take the one nearest the shopkeeper."""
    acts = [a for a in sv.call("actions") if keyword in a["action"]]
    if not acts: return None
    a = sv.call("around", r=60)
    n = next((x for x in a["npcs"] if x.get("name") == npc), None)
    if n:
        acts.sort(key=lambda t: abs(t["x"] - n["x"]) + abs(t["y"] - n["y"]))
    act.log(f"counter {keyword}: {[(t['x'], t['y'], t['action']) for t in acts[:4]]}, {npc} at {n and (n['x'], n['y'])}")
    return acts[0]

GEO_NEEDS = {"Quartz", "Earth Crystal", "Frozen Tear", "Fire Quartz", "Aquamarine", "Nautilus Shell"}

def geodes():
    """Clint cracks geodes for 25g each (wiki: Blacksmith, open 9:00-16:00). Geode -> Quartz/Earth Crystal etc."""
    import needs, town
    s = sv.state()
    if not (900 <= s["time"] < 1400) or s["player"]["money"] < 400:
        return
    q = needs.quota()
    if not (GEO_NEEDS & set(q)):
        return
    p = _prog(); ch = p.get("chest", {})
    kinds = [g for g in ("Geode", "Frozen Geode", "Magma Geode", "Omni Geode") if ch.get(g, 0) + have(g) > 0]
    if not kinds or p.get("geode_day") == [s["season"], s["day"]]:
        return
    p["geode_day"] = [s["season"], s["day"]]; _save(p)
    if any(ch.get(g, 0) for g in kinds):
        donate.withdraw_bundle_items(set(kinds))
    act.goto("Blacksmith")
    c = counter("Blacksmith", "Clint")
    if not c:
        act.log("geodes: no counter tile"); return
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True)
    time.sleep(0.8)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    act.log(f"geodes: dialogue options {[(r.get('name'), r.get('label')) for r in resp]}")
    if len(resp) < 2:
        town.close_menu(); act.dismiss(); return
    sv.call("click", x=resp[-2]["x"], y=resp[-2]["y"]); time.sleep(1.0)   # [..., Process, Leave]
    if (sv.state().get("menu") or {}).get("type") != "GeodeMenu":
        act.log(f"geodes: menu is {sv.state().get('menu')}"); town.close_menu(); return
    cracked = 0
    for _ in range(40):
        st = sv.state()
        if st["player"]["money"] < 300 or len(st["inventory"]) >= st.get("backpack", 12): break
        g = next((i for i in st["inventory"] if i["name"] in ("Geode", "Frozen Geode", "Magma Geode", "Omni Geode")), None)
        if not g: break
        w = next((x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] == g["slot"]), None)
        if not w: break
        # GeodeMenu: click the geode (picks the stack up), then click the anvil spot once per geode (Fa 8:
        # clicking only the inventory left the stack on the cursor and the menu refused to close)
        sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.4)
        spot = next((x for x in sv.widgets()["widgets"] if x["field"] == "geodeSpot"), None)
        if not spot: break
        for _ in range(30):
            st = sv.state()
            if st.get("held") not in ("Geode", "Frozen Geode", "Magma Geode", "Omni Geode") or st["player"]["money"] < 300: break
            sv.call("click", x=spot["x"], y=spot["y"]); time.sleep(2.5); cracked += 1
        if sv.state().get("held"):          # put any rest back into the backpack
            filled = {i["slot"] for i in sv.state()["inventory"]}
            e = [x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] not in filled and x["i"] < sv.state().get("backpack", 12)]
            if e: sv.call("click", x=e[0]["x"], y=e[0]["y"]); time.sleep(0.3)
        break
    ok = next((x for x in sv.widgets()["widgets"] if x["field"] == "okButton"), None)
    if ok: sv.call("click", x=ok["x"], y=ok["y"]); time.sleep(0.6)
    town.close_menu()
    found = sorted({i["name"] for i in sv.state()["inventory"]} & (GEO_NEEDS | {"Amethyst", "Topaz", "Jade", "Ruby", "Emerald", "Diamond"}))
    act.log(f"geodes: cracked {cracked}, holding {found}, money {sv.state()['player']['money']}")

def _clint_counter(option_index=None):
    """Right-click Clint's counter. option_index picks a response ([Shop, Upgrade, (Process), Leave])."""
    import town
    act.goto("Blacksmith")
    c = counter("Blacksmith", "Clint")
    if not c:
        return False
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    if option_index is None:
        return True
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if len(resp) <= option_index:
        act.log(f"clint: {len(resp)} options, menu {sv.state().get('menu')}"); act.dismiss(); town.close_menu(); return False
    sv.call("click", x=resp[option_index]["x"], y=resp[option_index]["y"]); time.sleep(1.0)
    return True

AXES = [("Axe", None, None, 0), ("Copper Axe", "Copper Bar", 2000, 1), ("Steel Axe", "Iron Bar", 5000, 2)]

def axe_tier():
    names = {i["name"] for i in act.inv()}
    return max((t for n, _, _, t in AXES if n in names), default=0)

def upgrade_axe():
    """Wiki (Blacksmith): Copper tool = 5 Copper Bars + 2,000g; Steel = 5 Iron Bars + 5,000g; 2 days each.
    Copper Axe: farm Large Stumps -> Hardwood (Construction). Steel Axe: the Large Log blocking the
    Secret Woods (Fiddlehead Fern for Chef's, summer only; Woodskip; respawning stumps)."""
    import needs, town
    s = sv.state(); p = _prog()
    abs_day = ["spring", "summer", "fall", "winter"].index(s["season"]) * 28 + s["day"]
    if p.get("axe_ready_day") is not None:
        if abs_day >= p["axe_ready_day"] and 900 <= s["time"] < 1400:
            _clint_counter()
            for _ in range(10):
                act.dismiss(); time.sleep(0.4)
            town.close_menu()
            if axe_tier() >= p.get("axe_target_tier", 1):
                p = _prog(); p.pop("axe_ready_day", None); p["copper_axe"] = True; _save(p)
                act.log(f"axe: picked up tier {axe_tier()} axe")
            else:
                act.log("axe: upgraded axe not received yet")
        return
    tier = axe_tier()
    if tier == 0 and act.slot_of("Axe") is None:
        return                                      # axe is at Clint's
    q = needs.quota()
    # Steel Axe only while summer Fiddlehead Fern is still reachable (Woodskip alone can wait: Specialty needs Sandfish/bus)
    want_steel = "Fiddlehead Fern" in q and s["season"] == "summer" and s["day"] <= 26
    if tier >= 2 or (tier == 1 and not want_steel) or (tier == 0 and "Hardwood" not in q and not want_steel):
        return
    if not (900 <= s["time"] < 1400) or (s["day"] - 1) % 7 == 4:      # Clint 9-16, travel ~1 h
        return
    name, bar, cost, t = AXES[tier + 1]
    bars = have(bar) + p.get("chest", {}).get(bar, 0)
    if bars < 5 or s["player"]["money"] < cost + 300:
        return
    if have(bar) < 5:
        donate.withdraw_bundle_items({bar})
    if have(bar) < 5: return
    if not _clint_counter(1):
        return
    if (sv.state().get("menu") or {}).get("type") != "ShopMenu":
        act.log(f"axe: upgrade menu did not open ({sv.state().get('menu')})"); town.close_menu(); return
    time.sleep(0.6); town._last_shop = None
    sh = sv.call("shop"); act.log(f"axe: upgrade shop items {[it['name'] for it in sh['items']]}")
    m0 = s["player"]["money"]
    town.buy({name: 1})
    town.close_menu(); act.dismiss()
    if sv.state()["player"]["money"] <= m0 - cost:
        p = _prog(); p["axe_ready_day"] = abs_day + 2; p["axe_target_tier"] = t; _save(p)
        act.log(f"axe: {name} paid, ready day {abs_day + 2}")
    else:
        act.log(f"axe: {name} purchase did not go through")

def stumps(max_n=5):
    """Large Stumps -> Hardwood with the Copper Axe (Construction bundle)."""
    import needs
    q = needs.quota(); p = _prog()
    if not p.get("copper_axe") or "Hardwood" not in q: return
    need = q["Hardwood"] - p.get("chest", {}).get("Hardwood", 0) - have("Hardwood")
    if need <= 0 or sv.state()["player"]["stamina"] < 60: return
    act.goto("Farm", 64, 20)
    a = sv.call("around", r=80)
    _, me = act.here()
    st = sorted((c for c in a["clumps"] if c.get("id") == 600), key=lambda c: abs(c["x"]-me[0]) + abs(c["y"]-me[1]))
    for c in st[:max_n]:
        if have("Hardwood") >= need or sv.state()["player"]["stamina"] < 40: break
        t = (c["x"], c["y"])
        if act.walk(c["x"], c["y"] + 2, adjacent=False) != "arrived" and act.walk(c["x"] - 1, c["y"], adjacent=False) != "arrived":
            continue
        for _ in range(12):
            a2 = sv.call("around", r=4)
            if not any(cc["x"] == c["x"] and cc["y"] == c["y"] for cc in a2["clumps"]): break
            act.use(c["x"], c["y"] + 1, tool="Axe")
        farming.collect_debris(r=4)
        act.log(f"stump {t}: Hardwood now {have('Hardwood')}")

def buy_wood():
    """Wiki (Carpenter's Shop, Year 1): Wood 10g. Construction bundle needs 2 x 99 Wood.
    Robin's shop 9:00-17:00, closed Tuesday. Buy only with spare money (blueberries pay from Su 14)."""
    import needs, town
    s = sv.state(); q = needs.quota(); p = _prog()
    extra = machine_wood()
    if ("Wood" not in q and not jar_wanted() and not extra) or not (900 <= s["time"] < 1500) or (s["day"] - 1) % 7 == 1:
        return
    need = q.get("Wood", 0) + (55 if jar_wanted() else 0) + extra - p.get("chest", {}).get("Wood", 0) - have("Wood")   # margin: withdraw skips names already carried
    if need <= 0 or s["player"]["money"] < need * 10 + 1000:
        return
    act.goto("ScienceHouse")
    c = counter("Carpenter", "Robin")
    if not c:
        act.log(f"wood: no Carpenter tile {[a['action'] for a in sv.call('actions')][:6]}"); return
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if resp:
        sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(1.0)
    if (sv.state().get("menu") or {}).get("type") != "ShopMenu":
        act.log(f"wood: shop did not open ({sv.state().get('menu')})"); act.dismiss(); town.close_menu(); return
    time.sleep(0.6); town._last_shop = None
    town.buy({"Wood": need})
    town.close_menu()
    act.log(f"wood: bought, holding {have('Wood')} (bundle wants {q.get('Wood', 0)}, jar {jar_wanted()})")

def p_steel_pending():
    s = sv.state(); p = _prog()
    return axe_tier() == 1 and p.get("axe_ready_day") is None and s["season"] == "summer" and s["day"] <= 26

def vault():
    """Vault bundles are paid in gold from the Junimo note's purchase button (wiki: Bundles, Vault).
    Pay the cheapest open one once money covers it plus a reserve for seeds/axe/ores."""
    import needs, town
    cc = needs.live() or {}
    if (cc.get("completeBundles") or 0) < 4: return
    open_v = sorted((b for b in cc.get("bundles", []) if b["room"] == "Vault" and not b["complete"] and not b["ingredients"][0]["done"]),
                    key=lambda b: b["ingredients"][0]["stack"])
    if not open_v: return
    b = open_v[0]; amount = b["ingredients"][0]["stack"]
    s = sv.state()
    reserve = 3000 if s["season"] == "summer" and s["day"] < 25 else 1500
    if (s["season"] == "summer" and s["day"] >= 26) or (s["season"] == "fall" and s["day"] <= 2):
        reserve = 11000                       # Fall 1-2 seed money first (Pumpkin/Corn gold push, Cranberries)
    if p_steel_pending():
        reserve += 5300                       # keep the Steel Axe money (Fiddlehead window)
    if s["player"]["money"] < amount + reserve or s["time"] >= 1900: return
    act.goto("CommunityCenter")
    x, y = donate.NOTES["Vault"]
    act.walk(x, y, adjacent=True); act.use(x, y, right=True)
    try:
        sv.wait(lambda st: (st.get("menu") or {}).get("type") == "JunimoNoteMenu", timeout=4)
    except TimeoutError:
        act.log("vault: note did not open"); act.dismiss(); return
    info = sv.call("bundles")
    bb = next((x for x in info["bundles"] if x["name"] == b["name"]), None)
    if not bb:
        town.close_menu(); return
    sv.call("click", x=bb["x"], y=bb["y"]); time.sleep(0.8)
    pb = next((w for w in sv.widgets()["widgets"] if w["field"] == "purchaseButton"), None)
    m0 = sv.state()["player"]["money"]
    if pb:
        sv.call("click", x=pb["x"], y=pb["y"]); time.sleep(1.5)
    act.dismiss()
    for _ in range(5):
        if (sv.state().get("menu") or {}).get("type") != "JunimoNoteMenu": break
        sv.call("tap", key="Escape", ticks=6); time.sleep(0.8)
    town.close_menu()
    paid = m0 - sv.state()["player"]["money"]
    act.log(f"vault: {b['name']} " + (f"paid {paid}g" if paid >= amount else f"not paid (button {bool(pb)})"))

def attach_bait():
    """Inventory tab: pick up the Bait stack, click it onto the Fiberglass Rod (attaches, like a player)."""
    import town
    rod = act.slot_of("Fiberglass Rod"); bait = act.slot_of("Bait")
    if rod is None or bait is None: return
    if not sv.state().get("menu"):
        sv.call("tap", key="Escape", ticks=5); time.sleep(0.5)
    tab = next((x for x in sv.widgets()["widgets"] if x["field"] == "tabs" and x["name"] == "inventory"), None)
    if tab: sv.call("click", x=tab["x"], y=tab["y"]); time.sleep(0.4)
    w = {x["i"]: x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot"}
    if bait in w and rod in w:
        sv.call("click", x=w[bait]["x"], y=w[bait]["y"]); time.sleep(0.3)
        sv.call("click", x=w[rod]["x"], y=w[rod]["y"]); time.sleep(0.3)
        if act.slot_of("Bait") is None:
            act.log("bait attached to Fiberglass Rod")
        else:
            filled = {i["slot"] for i in sv.state()["inventory"]}
            e = [x for k, x in w.items() if k not in filled and k < sv.state().get("backpack", 12)]
            if e: sv.call("click", x=e[0]["x"], y=e[0]["y"]); time.sleep(0.3)
    town.close_menu()

def buy_rod():
    """Wiki: Fiberglass Rod 1,800g (Willy, Fishing 2) takes bait; Bait halves the bite delay and lowers trash.
    Willy 9:00-17:00, no sales on non-rainy Saturdays. Bait: Willy 5g, or craft from Bug Meat."""
    import town
    s = sv.state()
    if any(i["name"] == "Fiberglass Rod" for i in act.inv()):
        if act.slot_of("Bait") is None and _prog().get("chest", {}).get("Bait"):
            act.goto("Farm"); donate.withdraw_bundle_items({"Bait"})
        if act.slot_of("Bait") is None and (_prog().get("chest", {}).get("Bug Meat") or have("Bug Meat")):
            if not have("Bug Meat"): act.goto("Farm"); donate.withdraw_bundle_items({"Bug Meat"})
            if have("Bug Meat"): craft.craft("Bait", n=min(have("Bug Meat"), 40))
        attach_bait(); return
    if s["player"]["money"] < 1800 + 2500 or not (900 <= s["time"] < 1500) or (s["day"] % 7 == 6 and s["weather"] == "sun"):
        return
    if s["player"]["skills"]["fishing"] < 2: return
    try:
        town.open_shop("FishShop", action_prefix="Buy")
    except LookupError as e:
        act.log(f"rod: {e}"); return
    town.buy({"Fiberglass Rod": 1, "Bait": 60})
    town.close_menu()
    act.log(f"rod: Fiberglass Rod {'bought' if act.slot_of('Fiberglass Rod') is not None else 'NOT bought'}, money {sv.state()['player']['money']}")
    attach_bait()

FRUIT_CAT = -79   # wiki/Data: fruit category; Preserves Jar turns fruit into Jelly

def jar_wanted():
    import needs
    return "Jelly" in needs.quota() and not _prog().get("jar")

def jelly():
    """Artisan bundle: Jelly. Wiki: Preserves Jar (Farming 4 recipe) = 50 Wood + 40 Stone + 8 Coal; fruit -> Jelly
    in ~2-3 days. Fruit: Blackberry (Fa 8-11 forage), Wild Plum, Apple, Grape... any fruit no bundle needs."""
    import needs
    q = needs.quota(); p = _prog()
    if "Jelly" not in q and not p.get("jar"): return
    act.goto("Farm", CHEST[0], CHEST[1] + 2)
    if not p.get("jar"):
        need = {"Wood": 50, "Stone": 40, "Coal": 8}
        if any(have(k) < v for k, v in need.items()):
            donate.withdraw_bundle_items(set(need))
        if any(have(k) < v for k, v in need.items()):
            act.log(f"jar: missing {[(k, have(k)) for k, v in need.items() if have(k) < v]}"); return
        if craft.craft("Preserves Jar") < 1 or act.slot_of("Preserves Jar") is None:
            act.log("jar: craft failed"); return
        t = free_tile_near(CHEST[0] - 6, CHEST[1] + 1, avoid={CHEST} | set(furnaces()))
        craft.place("Preserves Jar", *t)
        if placed_ok("Preserves Jar", t):
            p = _prog(); p["jar"] = list(t); _save(p); act.log(f"jar placed at {t}")
        else:
            act.log(f"jar: place at {t} failed"); return
    t = tuple(_prog()["jar"])
    objs, _, _ = farming.tile_info(r=14)
    o = objs.get(t)
    if not o: act.log("jar missing"); return
    if o.get("ready"):
        act.walk(*t, adjacent=True); act.use(*t, right=True); time.sleep(0.4)
        act.log(f"jar: collected, Jelly {have('Jelly')}")
    if "Jelly" not in needs.quota(): return
    objs, _, _ = farming.tile_info(r=14)
    if objs.get(t, {}).get("held"):          # busy (mod reports held item if available)
        return
    hold = needs.quality_holds()
    fruit = [i for i in act.inv() if i.get("cat") == FRUIT_CAT and i["name"] not in q
             and not (i["name"] in hold and i.get("quality", 0) >= hold[i["name"]][0])]
    if fruit:
        f = fruit[0]; n0 = f["stack"]
        act.walk(*t, adjacent=True)
        sl = f["slot"] if f["slot"] < 12 else act.to_hotbar(f["name"], slot=f["slot"])
        if sl is not None and sl < 12:
            sv.call("use", x=t[0], y=t[1], slot=sl, right=True); act.wait_done("tool", 15)
        n1 = sum(i["stack"] for i in act.inv() if i["name"] == f["name"])
        act.log(f"jar: {'loaded ' + f['name'] if n1 < n0 else 'did not take ' + f['name']}")

def farm_cave():
    """Mushroom cave (Demetrius, chosen Su 23): 6 boxes, a mushroom every 2nd day (wiki: The Cave).
    Purple Mushroom -> Exotic + Field Research; Red -> Dye + Exotic; Morel -> Exotic."""
    s = sv.state()
    if s["time"] >= 2000: return
    # Amer W17 Y2: "why collecting mushrooms?" The bundles it served are done; now it is mine food + sale money.
    # Boxes fill every 2nd day, but the trip (~40 game min) ran daily and found 0 on alternate days. Go every 2nd day.
    import animals
    p = _prog(); today = animals._abs_day(s)
    if today is not None and p.get("cave_day") is not None and today - p["cave_day"] < 2: return
    act.goto("FarmCave")
    objs, _, _ = farming.tile_info(r=20)
    ready = [t for t, o in objs.items() if o.get("ready") or o.get("forage")]
    got = 0
    for t in sorted(ready):
        n0 = sum(i["stack"] for i in act.inv())
        if act.walk(*t, adjacent=True) != "arrived": continue
        act.use(*t, right=True); act.dismiss()
        if sum(i["stack"] for i in act.inv()) > n0: got += 1
    farming.collect_debris(r=10)
    if got and today is not None: p = _prog(); p["cave_day"] = today; _save(p)
    act.log(f"farm cave: collected {got} ({len(ready)} ready); held {[i['name'] for i in act.inv() if 'Mushroom' in i['name'] or i['name'] in ('Morel', 'Chanterelle')]}")

PICKS = [("Pickaxe", None, None, 0), ("Copper Pickaxe", "Copper Bar", 2000, 1), ("Steel Pickaxe", "Iron Bar", 5000, 2)]

def pick_tier():
    names = {i["name"] for i in act.inv()}
    return max((t for n, _, _, t in PICKS if n in names), default=-1)

def upgrade_pickaxe():
    """Session 4: mining is the winter bottleneck (Geologist's, Adventurer's, Frozen Geode, Aquamarine; lift only 15
    after 18 mine days). Wiki (Blacksmith / Tools): Copper Pickaxe 2,000g + 5 Copper Bars, Steel 5,000g + 5 Iron Bars,
    2 days at Clint. Done in fall so the winter mining days keep a pickaxe."""
    import town
    s = sv.state(); p = _prog()
    abs_day = ["spring", "summer", "fall", "winter"].index(s["season"]) * 28 + s["day"]
    if p.get("pick_ready_day") is not None:
        if abs_day >= p["pick_ready_day"] and 900 <= s["time"] < 1500 and (s["day"] - 1) % 7 != 4:
            _clint_counter()
            for _ in range(10):
                act.dismiss(); time.sleep(0.4)
            town.close_menu()
            if pick_tier() >= p.get("pick_target_tier", 1):
                p = _prog(); p.pop("pick_ready_day", None); _save(p)
                act.log(f"pickaxe: picked up tier {pick_tier()} pickaxe")
            else:
                act.log("pickaxe: upgraded pickaxe not received yet")
        return
    tier = pick_tier()
    if tier < 0 or tier >= 2: return                 # at Clint's, or Steel already
    if not (900 <= s["time"] < 1400) or (s["day"] - 1) % 7 == 4: return
    if s["season"] == "winter" and s["day"] > 20: return
    name, bar, cost, t = PICKS[tier + 1]
    bars = have(bar) + p.get("chest", {}).get(bar, 0)
    if bars < 5 or s["player"]["money"] < cost + 1500:
        return
    if have(bar) < 5:
        donate.withdraw_bundle_items({bar})
    if have(bar) < 5:
        act.log(f"pickaxe: only {have(bar)} {bar} in backpack"); return
    if not _clint_counter(1):
        return
    if (sv.state().get("menu") or {}).get("type") != "ShopMenu":
        act.log(f"pickaxe: upgrade menu did not open ({sv.state().get('menu')})"); town.close_menu(); return
    time.sleep(0.6); town._last_shop = None
    sh = sv.call("shop"); act.log(f"pickaxe: upgrade shop items {[it['name'] for it in sh['items']]}")
    m0 = s["player"]["money"]
    town.buy({name: 1})
    town.close_menu(); act.dismiss()
    if sv.state()["player"]["money"] <= m0 - cost:
        p = _prog(); p["pick_ready_day"] = abs_day + 2; p["pick_target_tier"] = t; _save(p)
        act.log(f"pickaxe: {name} paid, ready day {abs_day + 2}")
    else:
        act.log(f"pickaxe: {name} purchase did not go through")

def buy_hay():
    """Fodder bundle: 10 Hay. Wiki (Hay / Marnie's Ranch): 50g at Marnie's, shop 9:00-16:00, closed Mon/Tue,
    Fall 18, Winter 18. One trip; the hay goes to the chest with the other bundle items."""
    import needs, town
    s = sv.state(); q = needs.quota(); p = _prog()
    need = q.get("Hay", 0) - p.get("chest", {}).get("Hay", 0) - have("Hay")
    if need <= 0 or not (900 <= s["time"] < 1500) or (s["day"] - 1) % 7 in (0, 1) or s["day"] == 18:
        return
    if s["player"]["money"] < need * 50 + 1500 or len(act.inv()) >= s.get("backpack", 12):
        return
    act.goto("AnimalShop")
    c = counter("AnimalShop", "Marnie")
    if not c:
        act.log(f"hay: no AnimalShop tile {[a['action'] for a in sv.call('actions')][:6]}"); return
    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if resp:
        sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(1.0)      # Supplies Shop
    if (sv.state().get("menu") or {}).get("type") != "ShopMenu":
        act.log(f"hay: shop did not open ({sv.state().get('menu')})"); act.dismiss(); town.close_menu(); return
    time.sleep(0.6); town._last_shop = None
    h0, m0 = have("Hay"), sv.state()["player"]["money"]
    town.buy({"Hay": need})
    town.close_menu()
    act.log(f"hay: holding {h0} -> {have('Hay')}, money {m0} -> {sv.state()['player']['money']}")

# ---------- Session 4: tappers -> Oak Resin -> Keg -> Wine (Enchanter's), Maple Syrup (Chef's / Bee House) ----------
TREE_KIND = {"Oak Resin": "1", "Maple Syrup": "2"}        # Tree.treeType: 1 oak, 2 maple, 3 pine (decompiled Tree)

def _keg_wanted():
    import needs
    return "Wine" in needs.quota() and not _prog().get("keg")

def tapper_wants():
    """Products a tapper should make: Maple Syrup while a bundle needs it, Oak Resin while the keg is unbuilt.
    Wiki (Tapper, 1.6): recipe learned at Foraging level 4 (was 3 before 1.6)."""
    import needs
    if sv.state()["player"]["skills"].get("foraging", 0) < 4: return []
    q = needs.quota(); have_t = {k for k, _ in (_prog().get("tappers") or {}).items()}
    want = []
    if "Maple Syrup" in q and "Maple Syrup" not in have_t: want.append("Maple Syrup")
    if _keg_wanted() and have("Oak Resin") + _prog().get("chest", {}).get("Oak Resin", 0) < 1 and "Oak Resin" not in have_t:
        want.append("Oak Resin")
    return want

def machine_wood():
    """Extra wood buy_wood should fetch for machines (wiki: Tapper 40 Wood + 2 Copper Bars; Keg 30 Wood + Copper + Iron Bar + Oak Resin)."""
    return 40 * len(tapper_wants()) + (30 if _keg_wanted() else 0)

def tappers():
    s = sv.state()
    if s["time"] >= 1700: return
    p = _prog(); taps = p.get("tappers") or {}
    # collect ready tappers
    if taps:
        act.goto("Farm", 64, 20)
        objs, _, _ = farming.tile_info(r=60)
        for prod, t in list(taps.items()):
            o = objs.get(tuple(t))
            if not o or o["name"] != "Tapper":
                act.log(f"tapper for {prod} missing at {t}"); taps.pop(prod); continue
            if o.get("ready"):
                n0 = have(prod)
                act.walk(*t, adjacent=True); act.use(*t, right=True); time.sleep(0.4)
                act.log(f"tapper {t}: collected {prod} {n0} -> {have(prod)}")
                import needs
                if prod not in needs.quota() and not (prod == "Oak Resin" and _keg_wanted()):
                    pass                                   # keep tapping: syrup/resin feed later machines
        p = _prog(); p["tappers"] = taps; _save(p)
    for prod in tapper_wants():
        if have("Tapper") < 1 and _prog().get("chest", {}).get("Tapper"):
            donate.withdraw_bundle_items({"Tapper"})
        if have("Tapper") < 1:
            need = {"Wood": 40, "Copper Bar": 2}
            if any(have(k) < v for k, v in need.items()):
                donate.withdraw_bundle_items(set(need))
            if any(have(k) < v for k, v in need.items()):
                act.log(f"tapper: missing {[(k, have(k)) for k, v in need.items() if have(k) < v]}"); return
            if craft.craft("Tapper") < 1 or act.slot_of("Tapper") is None:
                act.log("tapper: craft failed (recipe: Foraging 3)"); return
        act.goto("Farm", 64, 20)
        _, feats, _ = farming.tile_info(r=60)
        _, me = act.here()
        used = {tuple(t) for t in taps.values()}
        trees = sorted((t for t, f in feats.items() if f["type"] == "Tree" and str(f.get("tree")) == TREE_KIND[prod]
                        and f.get("stage", 0) >= 5 and t not in used),
                       key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]))
        if not trees:
            act.log(f"tapper: no mature {prod} tree within 60 tiles"); continue
        for t in trees[:4]:
            if act.walk(*t, adjacent=True) != "arrived":
                try:
                    if farming.approach(t) != "arrived": continue
                except LookupError:
                    continue                  # needs a tool that is at Clint's
            act.use(*t, tool="Tapper"); time.sleep(0.4)
            if placed_ok("Tapper", t):
                taps[prod] = list(t); p = _prog(); p["tappers"] = taps; _save(p)
                act.log(f"tapper placed on {prod} tree {t}"); break
            act.log(f"tapper: place on {t} failed")

def keg():
    """Wine for Enchanter's (and The Missing). Keg = Farming 8 recipe; fruit -> Wine in 7 days (wiki Keg)."""
    import needs
    q = needs.quota(); p = _prog()
    if "Wine" not in q and not p.get("keg"): return
    if sv.state()["time"] >= 1700: return
    if not p.get("keg"):
        if have("Keg") < 1 and (p.get("chest") or {}).get("Keg"):
            donate.withdraw_bundle_items({"Keg"})         # W18: 2 kegs crafted on failed placements sat in the chest
        if have("Keg") < 1:
            need = {"Wood": 30, "Copper Bar": 1, "Iron Bar": 1, "Oak Resin": 1}
            if any(have(k) < v for k, v in need.items()):
                donate.withdraw_bundle_items(set(need))
            if any(have(k) < v for k, v in need.items()):
                return
            act.goto("Farm", CHEST[0], CHEST[1] + 2)
            if craft.craft("Keg") < 1 or act.slot_of("Keg") is None:
                act.log("keg: craft failed"); return
        act.goto("Farm", CHEST[0], CHEST[1] + 2)
        # W18: tiles by the porch (65,15) refused placement; use the open ground south-west of the furnaces
        t = free_tile_near(CHEST[0] - 4, CHEST[1] + 4, r=5, avoid={CHEST} | set(furnaces()) | {tuple(p.get("jar") or (0, 0))})
        craft.place("Keg", *t)
        if placed_ok("Keg", t):
            p = _prog(); p["keg"] = list(t); _save(p); act.log(f"keg placed at {t}")
        else:
            act.log(f"keg: place at {t} failed"); return
    t = tuple(_prog()["keg"])
    act.goto("Farm", CHEST[0], CHEST[1] + 2)
    objs, _, _ = farming.tile_info(r=16)
    o = objs.get(t)
    if not o: act.log("keg missing"); return
    if o.get("ready"):
        act.walk(*t, adjacent=True); act.use(*t, right=True); time.sleep(0.4)
        act.log(f"keg: collected, Wine {have('Wine')}")
    if "Wine" not in needs.quota(): return
    objs, _, _ = farming.tile_info(r=16)
    if objs.get(t, {}).get("held"): return
    hold = needs.quality_holds()
    fruit = [i for i in act.inv() if i.get("cat") == FRUIT_CAT and i["name"] not in q
             and not (i["name"] in hold and i.get("quality", 0) >= hold[i["name"]][0])]
    if fruit:
        f = min(fruit, key=lambda i: i.get("price", 0)); n0 = f["stack"]
        act.walk(*t, adjacent=True)
        sl = f["slot"] if f["slot"] < 12 else act.to_hotbar(f["name"], slot=f["slot"])
        if sl is not None and sl < 12:
            sv.call("use", x=t[0], y=t[1], slot=sl, right=True); act.wait_done("tool", 15)
        n1 = sum(i["stack"] for i in act.inv() if i["name"] == f["name"])
        act.log(f"keg: {'loaded ' + f['name'] if n1 < n0 else 'did not take ' + f['name']}")
    else:
        act.log("keg: no spare fruit to load")
