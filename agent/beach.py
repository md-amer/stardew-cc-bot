"""Sea Urchin (Dye bundle). Wiki Sea Urchin / Tide Pools: found year-round in the Beach tide pools east of the
wooden footbridge (20% of tide-pool forage); the footbridge is broken until repaired with 300 Wood.
Map action tile: Beach (58,13) "BrokenBeachBridge"."""
import time
import sv, act, town, needs

BRIDGE = (58, 13)


def _prog():
    import play_day; return play_day.prog()


def _save(p):
    import play_day; play_day.save_prog(p)


def _wood():
    return sum(i["stack"] for i in act.inv() if i["name"] == "Wood")


def repair_bridge():
    p = _prog()
    if p.get("beach_bridge"): return True
    if _wood() < 300:
        import donate
        donate.withdraw_bundle_items({"Wood"})
    if _wood() < 300:
        act.log(f"beach: need 300 Wood for the bridge, have {_wood()}"); return False
    act.goto("Beach")
    act.walk(*BRIDGE, adjacent=True)
    act.use(*BRIDGE, right=True); time.sleep(0.8)
    for _ in range(10):
        resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
        if resp: break
        time.sleep(0.3)
    if not resp:
        act.log(f"beach: no bridge question ({sv.state().get('menu')})"); act.dismiss(); return False
    w0 = _wood()
    sv.call("mouse", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(0.3)
    sv.call("click", x=resp[0]["x"], y=resp[0]["y"]); time.sleep(1.0)       # first answer = Yes
    act.dismiss()
    ok = _wood() <= w0 - 300
    act.log(f"beach: bridge {'REPAIRED' if ok else 'not repaired'} (wood {w0} -> {_wood()})")
    if ok:
        p = _prog(); p["beach_bridge"] = True; _save(p)
    return ok


def tide_pools():
    """Forage the tide pools (east of the bridge) for Sea Urchins."""
    if "Sea Urchin" not in needs.quota(): return
    s = sv.state()
    if s["time"] >= 1700: return
    if not repair_bridge(): return
    st = sv.state()
    if st.get("backpack", 12) - len(st["inventory"]) < 3:      # Fa 23 Y2: 5 tide-pool items skipped, backpack full
        import play_day; play_day.chest_sync_and_ship()
    act.goto("Beach")
    act.walk(BRIDGE[0] + 6, BRIDGE[1] + 6) == "arrived" or act.walk(BRIDGE[0] + 3, BRIDGE[1] + 3)
    n = town.forage_nearby(r=30, max_items=20)
    have = any(i["name"] == "Sea Urchin" for i in act.inv())
    act.log(f"beach: tide pools foraged {n}; Sea Urchin {'GOT' if have else 'none today'}")
