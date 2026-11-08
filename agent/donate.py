"""Donate held items to Community Center bundles through the Junimo note UI."""
import time
import sv, act, town, craft, needs

NOTES = {"Pantry": (14, 5), "Crafts Room": (14, 23), "Fish Tank": (40, 10),
         "Boiler Room": (63, 14), "Vault": (55, 6), "Bulletin Board": (46, 12)}
CHEST = (74, 14)

@act.slow
def withdraw_bundle_items(bring):
    """Take only the stacks this trip can donate (open rooms) out of the chest."""
    act.goto("Farm")
    act.walk(*CHEST, adjacent=True)
    act.use(*CHEST, right=True)
    sv.wait(lambda s: (s.get("menu") or {}).get("type") == "ItemGrabMenu", timeout=5)
    took = []
    for name in sorted(bring):
        # a carried stack of the same name still gets the chest's part (Fa 24: 9 Hay held + 1 in chest = 0 donated)
        n0 = sum(i["stack"] for i in sv.state()["inventory"] if i["name"] == name)
        if not n0 and len(sv.state()["inventory"]) >= sv.state().get("backpack", 12):
            continue
        # re-read the chest every time: it compacts after each take, so old slot indexes go stale
        it = next((g for g in sv.state()["menu"].get("grab", []) if g["name"] == name), None)
        if not it:
            continue
        w = next(x for x in sv.widgets()["widgets"] if x["field"] == "ItemsToGrabMenu.slot" and x["i"] == it["i"])
        sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.25)
        if sum(i["stack"] for i in sv.state()["inventory"] if i["name"] == name) > n0:
            took.append(name)
        else:
            act.log(f"withdraw {name}: click did not move it")
    town.close_menu()
    # extra chests (materials): take what the main chest did not have
    for xy in craft.extra_chests():
        # materials (Wood, Stone...) are spread over chests: always top up from the extra chests too (Fa 3 Y2)
        rest = [n for n in sorted(bring) if n not in took or n in ("Wood", "Stone", "Clay", "Coal", "Fiber", "Hardwood")]
        if not rest: break
        craft._open(xy)
        for name in rest:
            if len(sv.state()["inventory"]) >= sv.state().get("backpack", 12) and not any(i["name"] == name for i in sv.state()["inventory"]):
                continue
            it = next((g for g in sv.state()["menu"].get("grab", []) if g["name"] == name), None)
            if not it: continue
            w = next(x for x in sv.widgets()["widgets"] if x["field"] == "ItemsToGrabMenu.slot" and x["i"] == it["i"])
            sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.25); took.append(name)
        craft._record(xy, craft._grab_contents())
        town.close_menu()
    act.log(f"withdrew for bundles: {took}")
    return took

def _wait_free(n=40):
    """A completed bundle can open a new room: the camera pans to the new note (player frozen)."""
    for _ in range(n):
        st = act.dismiss()
        if st.get("free") and not st.get("event"):
            return
        time.sleep(0.4)

@act.slow
def _best_stacks():
    """name -> the highest-quality stack in the backpack (quality ingredients need gold stacks)."""
    out = {}
    for i in sv.state()["inventory"]:
        o = out.get(i["name"])
        if not o or (i.get("quality", 0), i["stack"]) > (o.get("quality", 0), o["stack"]):
            out[i["name"]] = i
    return out

def donate_room(room):
    x0, y0 = NOTES[room]
    cands = [(x0, y0), (x0, y0 + 1), (x0 - 1, y0), (x0 + 1, y0), (x0, y0 - 1), (x0 - 1, y0 + 1), (x0 + 1, y0 + 1)]
    opened = False
    for x, y in cands:                    # Bulletin Board note did not open at its listed tile (Su 5-6): probe neighbours
        _wait_free()
        if act.walk(x, y, adjacent=True) != "arrived": continue
        act.use(x, y, right=True)
        try:
            sv.wait(lambda s: (s.get("menu") or {}).get("type") == "JunimoNoteMenu", timeout=3)
            opened = True
            if (x, y) != (x0, y0):
                act.log(f"donate: {room} note opened at {(x, y)} (listed {(x0, y0)})"); NOTES[room] = (x, y)
            break
        except TimeoutError:
            act.dismiss()
    if not opened:
        act.log(f"donate: note in {room} did not open"); return 0
    x, y = NOTES[room]
    given = 0
    info = sv.call("bundles")
    for b in info["bundles"]:
        if b["complete"]:
            continue
        inv = _best_stacks()
        want = [g for g in b["ingredients"] if not g["done"] and g["name"] in inv
                and inv[g["name"]]["stack"] >= g["stack"] and inv[g["name"]]["quality"] >= g["quality"]]
        if not want:
            continue
        sv.call("click", x=b["x"], y=b["y"]); time.sleep(0.6)        # open bundle page
        for g in want:
            inv = _best_stacks()
            it = inv.get(g["name"])
            if not it: continue
            w = next((x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] == it["slot"]), None)
            if w:
                sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.4)          # pick up
                # drop into the first EMPTY ingredient slot (slots fill left to right; filled ones refuse)
                done_n = sum(1 for gg in b["ingredients"] if gg["done"])
                cur = sv.call("bundles")
                if cur:
                    cb = next((bb for bb in cur["bundles"] if bb["name"] == b["name"]), None)
                    if cb: done_n = sum(1 for gg in cb["ingredients"] if gg["done"])
                slots = [x for x in sv.widgets()["widgets"] if x["field"] == "ingredientSlots"]
                slot = slots[min(done_n, len(slots) - 1)] if slots else None
                if slot:
                    sv.call("click", x=slot["x"], y=slot["y"]); time.sleep(0.6)  # drop into bundle
                # remainder of the stack stays on the cursor: drop it back into an empty slot
                filled = {i["slot"] for i in sv.state()["inventory"]}
                e = [x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] not in filled and x["i"] < sv.state().get("backpack", 12)]
                if e: sv.call("click", x=e[0]["x"], y=e[0]["y"]); time.sleep(0.3)
                after = {i["name"]: i["stack"] for i in sv.state()["inventory"]}
                if after.get(g["name"], 0) < it["stack"]:
                    given += 1
                    act.log(f"donated {g['name']} x{g['stack']} -> {b['name']}")
                else:
                    # not accepted: put it back so the menu can close
                    filled = {i["slot"] for i in sv.state()["inventory"]}
                    e = [x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] not in filled]
                    if e: sv.call("click", x=e[0]["x"], y=e[0]["y"]); time.sleep(0.3)
                    act.log(f"bundle refused {g['name']}")
        time.sleep(1.0)
        # back to the room page (bundle may have completed with an animation)
        for _ in range(5):
            st = sv.call("bundles")
            if not st or not st["specific"]:
                break
            sv.call("tap", key="Escape", ticks=6)          # menu key: bundle page -> room page
            time.sleep(0.8)
        if (sv.state().get("menu") or {}).get("type") != "JunimoNoteMenu":
            act.use(x, y, right=True); time.sleep(0.6)
    town.close_menu()
    return given

def donate_all(chest=None):
    """Plan from live bundle state: bring only items for open (or about-to-open) rooms."""
    have = dict(chest or {})
    for i in act.inv():
        have[i["name"]] = have.get(i["name"], 0) + i["stack"]
    have_q = {}
    for i in act.inv():
        have_q.setdefault(i["name"], {})
        have_q[i["name"]][i.get("quality", 0)] = have_q[i["name"]].get(i.get("quality", 0), 0) + i["stack"]
    bring, rooms = needs.donation_plan(have, have_q=have_q)
    if not rooms:
        act.log("donate: nothing donatable in open rooms"); return 0
    act.log(f"donate plan: {sorted(bring)} -> {rooms}")
    import json, os
    try: in_chest = dict(chest or json.load(open(os.path.join(os.path.dirname(__file__), "progress.json"))).get("chest", {}))
    except Exception: in_chest = {}
    from_chest = {n for n in bring if in_chest.get(n)}
    if from_chest:
        # W9 Y2: backpack full (0 free) -> withdraw took nothing, the trip to the CC donated 0 (Quartz stayed home)
        carried = {i["name"] for i in act.inv()}
        free = sv.state().get("backpack", 12) - len(act.inv())
        if free < len(from_chest - carried):
            act.log(f"donate: {free} free slots for {len(from_chest - carried)} chest items: emptying backpack first")
            import play_day; play_day.chest_sync_and_ship()
        withdraw_bundle_items(from_chest)
    if not any(i["name"] in bring for i in act.inv()):
        act.log(f"donate: none of {sorted(bring)} carried after withdraw: skipping the CC trip"); return 0
    act.goto("CommunityCenter")
    total = 0
    for room in rooms:
        try:
            total += donate_room(room)
        except Exception as e:
            act.log(f"donate {room} failed: {e!r}")
            town.close_menu()
    cc = needs.live() or {}
    try:
        import json, os; json.dump(cc, open(os.path.join(act.ROOT, "stats", "cc.json"), "w"))   # dashboard cache
    except Exception:
        pass
    act.log(f"donated {total} items; complete bundles now {cc.get('completeBundles')}")
    return total
