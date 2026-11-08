"""Maki Roll for the Chef's bundle (Amer: absolute minimum, CC asap).
Wiki (Maki Roll, Stardrop Saloon, Cookout Kit, Pierre's, Blacksmith):
- Gus may sell Maki Roll as the dish of the day (440g): check the Saloon shop first.
- Else: recipe at the Saloon 300g; ingredients Any Fish + Seaweed + Rice (Pierre 200g).
- No kitchen: Cookout Kit (Foraging 3): Wood 15, Fiber 10, Coal 3 (Clint 150g each in Y2). Place it, use it to cook.
"""
import time
import sv, act, town, craft, needs


def _prog():
    import play_day; return play_day.prog()


def _save(p):
    import play_day; play_day.save_prog(p)


def _has(name):
    return sum(i["stack"] for i in act.inv() if i["name"] == name)


FISH_CAT = -4


def _open_gus():
    act.goto("Saloon")
    gus = next((n for n in sv.call("around", r=40)["npcs"] if n["name"] == "Gus"), None)
    if not gus:
        act.log("cook: Gus not in the Saloon"); return False
    for dy in (2, 1, 3):
        if act.walk(gus["x"], gus["y"] + dy) != "arrived": continue
        for ty in (gus["y"] + dy - 1, gus["y"]):
            act.use(gus["x"], ty, right=True); time.sleep(0.6)
            if (sv.state().get("menu") or {}).get("type") == "ShopMenu":
                time.sleep(0.4); return True
            act.dismiss()
    return False


def saloon_visit():
    """Buy Maki Roll if it is the dish of the day; buy the recipe once. Returns True if a Maki Roll is held."""
    s = sv.state()
    if not (1200 <= s["time"] < 2300): return False
    try:
        town.open_shop("Saloon")
    except Exception as e:
        # Fa 20 Y2: no "Buy" tile in the 1.6 Saloon map. Decompiled GameLocation.saloon(): the shop opens when the
        # player (below the bar) interacts while Gus stands in the bar area (9..18, 17..18). Click Gus from below.
        if not _open_gus():
            act.log(f"cook: Saloon shop did not open ({e!r})"); return False
    items = {it["name"]: it for it in (sv.call("shop") or {}).get("items", [])}
    if "Maki Roll" in items:
        town.buy({"Maki Roll": 1})
        act.log("cook: bought Maki Roll (dish of the day)")
    p = _prog()
    if not p.get("maki_recipe") and _has("Maki Roll") == 0:
        rec = next((n for n in items if n.startswith("Maki Roll") and "Recipe" in n), None)
        if rec:
            m0 = sv.state()["player"]["money"]
            town.buy({rec: 1})
            if sv.state()["player"]["money"] < m0:
                p = _prog(); p["maki_recipe"] = True; _save(p); act.log("cook: Maki Roll recipe learned")
        else:
            act.log(f"cook: no Maki Roll recipe in the Saloon stock ({list(items)[:8]})")
    town.close_menu()
    return _has("Maki Roll") > 0


def cook_maki():
    """Cook one Maki Roll on a Cookout Kit placed on the farm."""
    if _has("Maki Roll") or not _prog().get("maki_recipe"): return
    if not any(i.get("cat") == FISH_CAT for i in act.inv()):
        act.log("cook: no fish for Maki Roll"); return
    if not _has("Seaweed"):
        act.log("cook: no Seaweed (ocean fishing)"); return
    st = sv.state()
    if st.get("backpack", 12) - len(st["inventory"]) < 3:     # Fa 25 Y2: "buy Rice: backpack full"
        import play_day; play_day.chest_sync_and_ship()
    if not _has("Rice"):
        t = sv.state()
        if t["time"] >= 1630 or (t["day"] - 1) % 7 == 2:     # Pierre 9-17, closed Wednesday (Fa 26: arrived 18:00)
            act.log("cook: Pierre closed, Rice tomorrow"); return
        town.open_shop("SeedShop"); town.buy({"Rice": 1}); town.close_menu()
    if not _has("Rice"):
        act.log("cook: Rice not bought"); return
    if not _has("Cookout Kit"):
        if _has("Coal") < 3:
            import donate; donate.withdraw_bundle_items({"Coal"})
        if _has("Coal") < 3:
            try:      # Clint's counter is "Blacksmith" + Shop answer (no Buy tile; projects.buy_ores)
                import projects
                if sv.state()["time"] < 900:     # W1-W2 Y2: Clint's door is locked before 9:00 (wiki): wait outside
                    act.goto("Town")
                    # W1-W2 Y2: wait_clock's 60 s real cap ended at 8:20, the locked door then timed out the warp
                    if not sv.wait_clock(900, max_real=300):
                        raise RuntimeError(f"still {sv.state()['time']} after waiting for 9:00")
                act.goto("Blacksmith")
                c = projects.counter("Blacksmith", "Clint")
                if c:
                    act.walk(c["x"], c["y"], adjacent=True); act.use(c["x"], c["y"], right=True); time.sleep(0.8)
                    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
                    if resp: sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(1.0)
                    if (sv.state().get("menu") or {}).get("type") == "ShopMenu":
                        time.sleep(0.6); town._last_shop = None
                        town.buy({"Coal": 3 - _has("Coal")})
                    town.close_menu()
            except Exception as e:
                act.log(f"cook: coal: {e!r}")
        if _has("Wood") < 15 or _has("Fiber") < 10:
            import donate; donate.withdraw_bundle_items({"Wood", "Fiber"})
        act.goto("Farm")
        if craft.craft("Cookout Kit") < 1:
            act.log(f"cook: cannot craft Cookout Kit (wood {_has('Wood')}, fiber {_has('Fiber')}, coal {_has('Coal')})"); return
    act.goto("Farm", 64, 20)
    import projects, farming
    # W3 Y2: blind placement at (me.x, me.y+2) failed (kit stayed in the backpack) -> menu None. Pick a free tile, verify.
    spot = None
    for _try in range(3):
        t = projects.free_tile_near(64, 22, r=6, avoid={spot} if spot else set())
        if not t: break
        n0 = _has("Cookout Kit")
        craft.place("Cookout Kit", *t); time.sleep(0.4)
        if _has("Cookout Kit") < n0:
            spot = t; break
        act.log(f"cook: kit placement at {t} failed"); spot = t
    if spot is None or _has("Cookout Kit"):
        objs, _, _ = farming.tile_info(r=4)
        act.log(f"cook: Cookout Kit not placed; objects near {[(k, v['name']) for k, v in objs.items()][:8]}"); return
    objs, _, _ = farming.tile_info(r=3)
    act.log(f"cook: kit placed at {spot}, object there = {(objs.get(tuple(spot)) or {}).get('name')}")
    act.walk(*spot, adjacent=True)
    act.use(*spot, right=True)
    try: sv.wait(lambda st: (st.get("menu") or {}).get("type") in ("GameMenu", "CraftingPage"), timeout=3)
    except TimeoutError: pass
    time.sleep(0.5)
    act.log(f"cook: menu after use = {(sv.state().get('menu') or {}).get('type')}")
    r = next((x for x in (sv.call("recipes") or []) if x["name"] == "Maki Roll"), None)
    if not r or not r.get("can"):
        act.log(f"cook: Maki Roll not cookable here ({r})"); town.close_menu(); return
    sv.call("click", x=r["x"], y=r["y"]); time.sleep(0.4)
    filled = {i["slot"] for i in sv.state()["inventory"]}
    e = [x for x in sv.widgets()["widgets"] if x["field"].endswith("inventory.slot") and x["i"] not in filled
         and x["i"] < sv.state().get("backpack", 12)]
    if e: sv.call("click", x=e[0]["x"], y=e[0]["y"]); time.sleep(0.3)
    town.close_menu()
    act.log(f"cook: Maki Roll {'COOKED' if _has('Maki Roll') else 'not cooked'}")


def step():
    if "Maki Roll" not in needs.quota(): return
    if _prog().get("maki_recipe"):
        cook_maki(); return          # recipe known: cook (the Saloon trip is only for the recipe / dish of the day)
    if not saloon_visit():
        cook_maki()
