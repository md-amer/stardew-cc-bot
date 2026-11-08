"""Calico Desert by bus (wiki: Bus Stop; needs the Vault room = bus repaired, mail "ccVault"). Ticket 500g at the
machine (Buildings tile 1057, decompiled BusStop.checkAction), Pam drives 10:00-17:00. Desert forage: Coconut,
Cactus Fruit (Exotic Foraging). Return: the bus tile action "DesertBus" -> Yes (first option)."""
import time
import sv, act, town, needs

def _prog():
    import play_day; return play_day.prog()

def _save(p):
    import play_day; play_day.save_prog(p)

def vault_done(cc):
    return all(b["ingredients"][0]["done"] for b in cc["bundles"] if b["room"] == "Vault")

def trip():
    s = sv.state()
    q = needs.quota()
    p0 = _prog()
    owned = {i["name"] for i in act.inv()} | {k for k, v in (p0.get("chest") or {}).items() if v}
    want = ({"Coconut", "Cactus Fruit", "Sandfish"} & set(q)) - owned     # Fa 27: went back for a Sandfish already in the chest
    # Amer (Su 20 Y2): "u can also get galaxy sword" - Prismatic Shard at the Three Pillars (wiki Galaxy Sword)
    if "Prismatic Shard" in owned and "Galaxy Sword" not in owned and not p0.get("galaxy_sword"):
        try:
            import fruit
            sap_pending = s["season"] == "summer" and s["day"] <= 27 and fruit.wanted()
        except Exception: sap_pending = False
        if not sap_pending:            # sapling money first (deadline Su 25/27); the 500g ticket can wait
            want = set(want) | {"Galaxy Sword"}
    if not want or not (1000 <= s["time"] < 1400) or s["player"]["money"] < 1500: return
    cc = needs.live() or {"bundles": []}
    if not vault_done(cc): return
    p = _prog()
    if p.get("desert_day") == [s["season"], s["day"]]: return
    if want <= {"Coconut", "Cactus Fruit"} and p.get("desert_day") == [s["season"], s["day"] - 1]: return   # forage respawns slowly
    p["desert_day"] = [s["season"], s["day"]]; _save(p)
    if "Galaxy Sword" in want and act.slot_of("Prismatic Shard") is None:
        import donate; donate.withdraw_bundle_items({"Prismatic Shard"})
    act.goto("BusStop")
    try:
        tiles = sv.call("find_tile", layer="Buildings", index=1057)
    except Exception as e:
        act.log(f"desert: find_tile unavailable ({e!r})"); return
    if not tiles: act.log("desert: no ticket machine tile"); return
    t = (tiles[0]["x"], tiles[0]["y"])
    act.walk(t[0], t[1] + 1) == "arrived" or act.walk(*t, adjacent=True)
    act.use(*t, right=True); time.sleep(1.0)
    resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
    if not resp:
        act.log(f"desert: no ticket question ({sv.state().get('menu')})"); act.dismiss(); return
    sv.call("click", x=resp[0]["x"], y=resp[0]["y"])      # Yes
    for _ in range(120):
        st = act.dismiss()
        if st["player"]["loc"] == "Desert" and st.get("free") and not st.get("event"): break
        time.sleep(0.5)
    if sv.state()["player"]["loc"] != "Desert":
        act.log("desert: did not arrive"); return
    if "Galaxy Sword" in want:
        try: galaxy_sword()
        except Exception as e: act.log(f"desert: galaxy sword failed {e!r}")
    if want & {"Coconut", "Cactus Fruit"}:
        n = town.forage_nearby(r=80, max_items=20)
        act.log(f"desert: foraged {n}; holding {[i['name'] for i in act.inv() if i['name'] in ('Coconut', 'Cactus Fruit')]}")
    if "Sandfish" in want:
        # wiki Sandfish: Desert pond, any season/weather, 6am-8pm. Fish until 16:00, then the 17:00 bus home.
        import daily
        try:
            got = False
            if daily.go_fish_spot_near(*act.here()[1], r=60):
                for _ in range(4):
                    daily.fish_session(until_time=1600, min_stamina=25, max_casts=60)
                    if "Sandfish" in {i["name"] for i in act.inv()}:
                        got = True; break
                    if sv.state()["time"] >= 1550: break
            act.log(f"desert: Sandfish {'CAUGHT' if got else 'not caught'}")
        except Exception as e:
            act.log(f"desert: fishing failed {e!r}")
    # The return bus is a Back-layer TouchAction "DesertBus" (decompiled Desert.performTouchAction): stepping on it asks
    # "Return to Stardew Valley?"; act.dismiss answers Yes. Fa 21: it fired with the farmer at (18,27).
    # touch actions fire on ENTERING the tile: step off first (Fa 22: standing on it already did nothing for 4 h)
    tiles = ((18, 29), (18, 27), (18, 29), (18, 28), (17, 29), (17, 27), (19, 29), (19, 27), (18, 26))
    try:
        bus_t = [(t["x"], t["y"]) for t in sv.call("touch_tiles") if t["action"].startswith("DesertBus")]
        if bus_t:
            b = bus_t[0]; tiles = ((b[0], b[1] + 2), b, (b[0] + 2, b[1]), b)
    except Exception:
        pass                                  # older mod build
    for t in tiles:
        if sv.state()["player"]["loc"] != "Desert": break
        try:
            act.walk(*t, timeout=20)          # the question pauses the walker: a timeout here is expected
        except TimeoutError:
            sv.call("stop")
        for _ in range(60):
            st = act.dismiss()
            if st["player"]["loc"] != "Desert" and st.get("free") and not st.get("event"): break
            time.sleep(0.5)
            if st["player"]["tile"][0] < 0: continue          # riding the bus (off-map x): keep waiting
            if st.get("free") and st["player"]["loc"] == "Desert" and not st.get("menu") and _ > 1: break
    bus = None
    if bus:
        for attempt in range(3):
            act.walk(bus["x"], bus["y"], adjacent=True); act.use(bus["x"], bus["y"], right=True)
            resp = []
            for _ in range(10):
                time.sleep(0.4)
                resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
                if resp: break
            if resp:
                sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); break     # Yes = first option
            act.log(f"desert: no return question (attempt {attempt + 1}, menu {sv.state().get('menu')})"); act.dismiss()
        for _ in range(120):
            st = act.dismiss()
            if st["player"]["loc"] != "Desert" and st.get("free") and not st.get("event"): break
            time.sleep(0.5)
    act.log(f"desert: back at {sv.state()['player']['loc']}")



def galaxy_sword():
    """Decompiled GameLocation.performTouchAction "legendarySword": stepping onto that Desert Back-layer tile while the
    active object is (O)74 Prismatic Shard gives the Galaxy Sword (shard consumed; 7 s real cutscene pause)."""
    if act.slot_of("Prismatic Shard") is None:
        act.log("desert: no Prismatic Shard in the backpack"); return
    tiles = [(t["x"], t["y"]) for t in sv.call("touch_tiles") if t["action"].startswith("legendarySword")]
    if not tiles:
        act.log("desert: no legendarySword tile found"); return
    t = tiles[0]
    act.walk(t[0], t[1] + 2) == "arrived" or act.walk(t[0], t[1], adjacent=True)
    # make the shard the active item: a harmless left-click use on our own tile selects its slot first (ToolTask)
    me = act.here()[1]
    try: act.use(me[0], me[1] + 1, tool="Prismatic Shard")
    except Exception as e: act.log(f"desert: selecting shard: {e!r}")
    act.walk(*t)                                   # touch actions fire on entering the tile
    for _ in range(40):
        st = act.dismiss()
        if "Galaxy Sword" in {i["name"] for i in act.inv()}: break
        time.sleep(0.5)
    got = "Galaxy Sword" in {i["name"] for i in act.inv()}
    act.log(f"desert: Galaxy Sword {'OBTAINED' if got else 'NOT obtained'} (tile {t})")
    if got:
        p = _prog(); p["galaxy_sword"] = True; _save(p)
